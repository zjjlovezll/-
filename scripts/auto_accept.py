"""One command that answers: is this checkout still trustworthy?

Run it before a commit, after a merge, or as a nightly job.  It checks the four things that
have actually broken in this project, in the order that costs least to fail:

    1. tests        the whole suite, because the frozen oracle and the architecture rules live
                    there; a green suite is the only claim nobody has to take on faith
    2. agent        the machine-facing layer's self-check: registry, case root, writable home
    3. contract     one tool call through the envelope, so a broken dispatch cannot hide
    4. end-to-end   one real simulation through the agent, which is the only check that proves
                    derive -> run -> read still works after a refactor

Every step reports its own verdict and the report is written as JSON, so a CI job or a
person can read the same thing.  Exit status is 0 only when every step passed.

    python scripts/auto_accept.py [--skip-run] [--report DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "src"
#: The frog window, resolved through ``velch.data_root`` rather than through the checkout: the
#: 1.4 GB corpus lives outside the package now, and a relative path here silently pointed at a
#: directory that no longer exists.
FAST_CASE_NAME = "case_frog_N_strip05.json"



def _invariants_step() -> dict[str, object]:
    """Re-derive the physics invariants from the archive and compare with the reference.

    Deliberately ``--no-run``: the whole suite already runs a simulation, and this step exists to
    catch a numbers drift, not to re-time the solver.  The full check (with one fresh run) is
    ``python scripts/physics_invariants.py``.
    """

    if _fast_case() is None:
        return {"step": "invariants", "ok": True, "skipped": True,
                "detail": {"reason": "语料未挂载（VELCH_DATA_ROOT）"}}
    command = [sys.executable, "-X", "utf8", str(REPO / "scripts" / "physics_invariants.py"),
               "--no-run"]
    started = time.perf_counter()
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", cwd=str(REPO),
                               env={**os.environ, "PYTHONPATH": str(SOURCE)})
    elapsed = time.perf_counter() - started
    tail = (completed.stdout + completed.stderr).strip().splitlines()[-3:]
    return {"step": "invariants", "ok": completed.returncode == 0,
            "detail": {"exit": completed.returncode, "seconds": round(elapsed, 1), "tail": tail},
            "seconds": round(elapsed, 1)}


def _fast_case() -> Path | None:
    """The smoke-test case, or ``None`` when the corpus is not mounted on this machine."""

    sys.path.insert(0, str(SOURCE))
    try:
        from velch.data_root import case_dir
    except Exception as exc:  # noqa: BLE001 - the gate must report, not crash
        print(f"auto_accept: cannot import velch.data_root: {exc}")
        return None
    path = case_dir() / FAST_CASE_NAME
    return path if path.is_file() else None



def _environment() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SOURCE) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONUTF8"] = "1"
    return env


def _run(name: str, program: list[str], *, timeout: float) -> dict:
    started = time.perf_counter()
    completed = subprocess.run(program, cwd=str(REPO), env=_environment(), capture_output=True,
                               text=True, timeout=timeout, check=False)
    elapsed = time.perf_counter() - started
    tail = (completed.stdout or "").strip().splitlines()[-3:]
    return {
        "step": name,
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "seconds": round(elapsed, 2),
        "command": " ".join(program[:6]),
        "tail": tail,
        "stderr_tail": (completed.stderr or "").strip().splitlines()[-3:],
    }


def _agent_call(payload: dict, *, timeout: float = 120.0) -> dict:
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "velch.agent", "call", json.dumps(payload)],
        cwd=str(REPO), env=_environment(), capture_output=True, text=True, timeout=timeout,
        check=False)
    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "raw": completed.stdout[-400:], "stderr": completed.stderr[-400:]}
    return envelope


def _run_end_to_end(steps: list[dict], case_path: Path) -> None:
    """Derive a case, run it through the job layer, and demand a manifest back.

    ``derive_case`` refuses a no-op on purpose ("nothing to derive"), so the smoke test has to
    perturb something.  Output sampling is the least invasive knob there is: it changes how often
    the dense solution is written out, not the solution itself, so a failure here is a plumbing
    failure and never a physics failure.
    """

    derived = _agent_call({"tool": "derive_case",
                           "arguments": {"parent": str(case_path), "tag": "auto-accept",
                                         "solver_patch": {"output_step_s": 0.001}}})
    if not derived.get("ok"):
        steps.append({"step": "end-to-end", "ok": False, "detail": derived.get("error")})
        return
    run = _agent_call({"tool": "submit_run",
                       "arguments": {"case": derived["data"]["path"], "workers": 1}},
                      timeout=1800)
    data = run.get("data") or {}
    steps.append({"step": "end-to-end", "ok": bool(run.get("ok")) and bool(data.get("manifest")),
                  "detail": {"status": data.get("status"),
                             "result_status": data.get("result_status"),
                             "job": data.get("job_id"),
                             "seconds": data.get("finished")}})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-run", action="store_true",
                        help="skip the end-to-end simulation (about 20 s on the frog window)")
    parser.add_argument("--report", type=Path, default=REPO / "reports",
                        help="directory for the JSON report")
    args = parser.parse_args(argv)

    steps: list[dict] = []
    steps.append(_run("tests", [sys.executable, "-X", "utf8", "-m", "pytest", "tests", "-q",
                                "--basetemp", str(Path(os.environ.get("TEMP", ".")) / "velch_accept")],
                      timeout=1800))
    steps.append(_run("doctor", [sys.executable, "-X", "utf8", "-m", "velch.agent", "doctor"],
                      timeout=120))

    capabilities = _agent_call({"tool": "capabilities"})
    steps.append({"step": "contract", "ok": bool(capabilities.get("ok")),
                  "detail": {"tools": len((capabilities.get("data") or {}).get("tools", []))}})

    steps.append(_invariants_step())
    series = subprocess.run([sys.executable, "-X", "utf8", str(REPO / "scripts" / "release_series.py"),
                             "--check"], cwd=REPO, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    steps.append({
        "step": "release-series",
        "ok": series.returncode == 0,
        "detail": (series.stdout or series.stderr).strip().splitlines()[-1]
                  if (series.stdout or series.stderr).strip() else "无输出",
    })

    if not args.skip_run:
        case_path = _fast_case()
        if case_path is None:
            # A fresh clone has the package but not the 1.4 GB corpus.  That is a weaker gate, not
            # a failing one — say so out loud instead of pretending the step ran.
            steps.append({"step": "end-to-end", "ok": True, "skipped": True,
                          "detail": {"reason": f"{FAST_CASE_NAME} 未挂载（VELCH_DATA_ROOT）"}})
        else:
            _run_end_to_end(steps, case_path)

    ok = all(step.get("ok") for step in steps)
    report = {
        "schema_version": "velch-auto-accept-v1",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "repository": str(REPO),
        "ok": ok,
        "steps": steps,
    }
    args.report.mkdir(parents=True, exist_ok=True)
    path = args.report / f"auto_accept_{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for step in steps:
        if step.get("skipped"):
            reason = (step.get("detail") or {}).get("reason", "")
            print(f"SKIP  {'      -':>8}  {step['step']}  {reason}")
            continue
        mark = "PASS" if step.get("ok") else "FAIL"
        seconds = f"{step['seconds']:7.1f}s" if "seconds" in step else "      -"
        print(f"{mark}  {seconds}  {step['step']}")
        if not step.get("ok"):
            for line in (step.get("tail") or []) + (step.get("stderr_tail") or []):
                print(f"        {line}")
            if step.get("detail"):
                print(f"        {json.dumps(step['detail'], ensure_ascii=False)[:400]}")
    print(f"\nreport: {path}")
    print("verdict:", "ACCEPT" if ok else "REJECT")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
