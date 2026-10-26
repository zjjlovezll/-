"""Can this package run a model on a machine that never saw this repository?

The installer is the deliverable, and until now nothing proved it.  ``smoke_test.py`` checks
that the frozen build *starts* and can run a corpus case, but it inherits this shell's
environment: ``VELCH_DATA_ROOT``, ``VELCH_VEHICLE_DIR`` and ``%LOCALAPPDATA%\\Velch`` all still
point at working things, so a build that only works because of them passes.

This script takes the opposite approach: copy the install folder somewhere neutral, then hand
the child process a **whitelisted** environment (not a filtered one) so no ``VELCH_*`` variable
survives by accident, and point ``LOCALAPPDATA`` at a scratch folder.  Then it requires:

1. ``vehicle list`` finds the five shipped models from inside the package;
2. the shipped portable case — flexible wheelset, ``lib:`` mode reference — runs end to end and
   the manifest says ``numerically_checked`` with every gate true;
3. the same run repeated after moving the copy to a path with Chinese characters and a space
   produces a **byte-identical** ``history.csv`` (a path must not reach the numbers);
4. ``--selftest`` exits 0 (the seven screens still build).

Usage::

    python -X utf8 packaging/clean_room_test.py --root dist_installer/Velch
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ("车辆 模型 中文 with space",)

WHITELIST = (
    "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "LANG", "PYTHONUTF8", "PYTHONIOENCODING",
)


def _environment(work: Path) -> dict[str, str]:
    """A whitelisted environment: nothing from this shell's VELCH_* setup can leak in."""

    clean = {name: os.environ[name] for name in WHITELIST if name in os.environ}
    clean["LOCALAPPDATA"] = str(work / "localappdata")
    clean["VELCH_UI_SCALE"] = "1"
    return clean


def _run(argv: list[str], *, env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=str(cwd), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=1800)


def _cli(folder: Path) -> Path:
    exe = folder / "velch-cli.exe"
    if not exe.is_file():
        raise SystemExit(f"no console build at {exe}")
    return exe


def step_vehicles(folder: Path, env: dict[str, str]) -> tuple[bool, str]:
    """Count model ids, not the word 自由度: two model *names* contain it (「六自由度」, 「纵向自由度」)."""

    result = _run([str(_cli(folder)), "vehicle", "list"], env=env, cwd=folder)
    text = result.stdout + result.stderr
    expected = ("CRH380A_M ", "CRH380A_M_6dof", "CRH380A_M_axlebox ", "CRH380A_M_axlebox_x", "CRH380A_M_node")
    listed = [name for name in expected if name in text]
    ok = result.returncode == 0 and len(listed) == len(expected) and "_internal" in text
    return ok, f"exit={result.returncode} models={len(listed)}/{len(expected)}"


def step_run(folder: Path, env: dict[str, str], work: Path, label: str) -> tuple[bool, str, str]:
    case = folder / "_internal" / "examples" / "portable" / "case_flexible.json"
    if not case.is_file():
        return False, f"missing {case}", ""
    out = work / f"out_{label}"
    result = _run([str(_cli(folder)), "run-vehicle", str(case), "--output", str(out), "--fast"],
                  env=env, cwd=folder)
    manifest = out / "manifest.json"
    history = out / "history.csv"
    if not manifest.is_file() or not history.is_file():
        return False, f"no artifacts (exit={result.returncode}) {(result.stderr or result.stdout)[-400:]}", ""
    payload = json.loads(manifest.read_text(encoding="utf-8-sig"))
    summary = payload.get("summary", {})
    status = summary.get("result_status")
    gates = summary.get("gates", {})
    ok = status == "numerically_checked" and bool(gates) and all(gates.values())
    digest = hashlib.sha256(history.read_bytes()).hexdigest()
    return ok, f"status={status} gates={sum(1 for v in gates.values() if v)}/{len(gates)}", digest


def step_selftest(folder: Path, env: dict[str, str]) -> tuple[bool, str]:
    result = _run([str(_cli(folder)), "--selftest"], env=env, cwd=folder)
    text = result.stdout + result.stderr
    ok = result.returncode == 0 and "加载失败" not in text
    return ok, f"exit={result.returncode}"


def step_bundled_corpus(folder: Path, env: dict[str, str], work: Path) -> tuple[bool, str]:
    """The package carries a corpus slice; no ``VELCH_DATA_ROOT`` may be needed to see it."""

    result = _run([str(_cli(folder)), "selfcheck"], env=env, cwd=folder)
    text = result.stdout + result.stderr
    line = next((row for row in text.splitlines() if "算例语料" in row), "")
    if "[PASS]" not in line:
        return False, f"selfcheck corpus line: {line.strip() or '(none)'}"
    case = folder / "_internal" / "portable" / "validation" / "crh380a_m" / "case_frog_N_strip05.json"
    if not case.is_file():
        return False, f"missing bundled case {case}"
    out = work / "out_bundled"
    ran = _run([str(_cli(folder)), "run-vehicle", str(case), "--output", str(out), "--fast"],
               env=env, cwd=folder)
    manifest = out / "manifest.json"
    if not manifest.is_file():
        return False, f"no manifest (exit={ran.returncode}) {(ran.stderr or ran.stdout)[-300:]}"
    payload = json.loads(manifest.read_text(encoding="utf-8-sig"))
    summary = payload.get("summary", {})
    gates = summary.get("gates", {})
    ok = summary.get("result_status") == "numerically_checked" and all(gates.values())
    return ok, f"{line.strip()[:40]} | status={summary.get('result_status')}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="dist_installer/Velch")
    parser.add_argument("--report", default="reports")
    args = parser.parse_args()

    source = (ROOT / args.root).resolve()
    if not source.is_dir():
        raise SystemExit(f"no install folder at {source}")

    started = time.time()
    work = Path(tempfile.mkdtemp(prefix="velch_cleanroom_"))
    steps: list[dict] = []
    digests: list[str] = []
    try:
        env = _environment(work)
        first = work / "install"
        shutil.copytree(source, first)

        for name, func in (("vehicles", lambda: step_vehicles(first, env)),
                           ("selftest", lambda: step_selftest(first, env)),
                           ("bundled-corpus", lambda: step_bundled_corpus(first, env, work))):
            ok, detail = func()
            steps.append({"step": name, "ok": ok, "detail": detail})

        ok, detail, digest = step_run(first, env, work, "plain")
        steps.append({"step": "run-plain-path", "ok": ok, "detail": detail})
        if digest:
            digests.append(digest)

        moved = work / CASES[0] / "install"
        moved.parent.mkdir(parents=True)
        shutil.move(str(first), str(moved))
        ok, detail, digest = step_run(moved, env, work, "unicode")
        steps.append({"step": "run-unicode-path", "ok": ok, "detail": detail})
        if digest:
            digests.append(digest)

        same = len(digests) == 2 and digests[0] == digests[1]
        steps.append({"step": "same-bytes-after-move", "ok": same,
                      "detail": "history.csv identical" if same else f"digests {digests}"})
    finally:
        shutil.rmtree(work, ignore_errors=True)

    failed = [item for item in steps if not item["ok"]]
    verdict = "ACCEPT" if not failed else "REJECT"
    report = {"verdict": verdict, "steps": steps, "elapsed_s": round(time.time() - started, 1),
              "source": str(source), "clean_environment": list(WHITELIST)}
    target = ROOT / args.report
    target.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = target / f"clean_room_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    for item in steps:
        print(f"[{'PASS' if item['ok'] else 'FAIL'}] {item['step']}: {item['detail']}")
    print(f"verdict: {verdict} · {len(steps)} 步 · 失败 {len(failed)}")
    print(f"报告：{path}")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
