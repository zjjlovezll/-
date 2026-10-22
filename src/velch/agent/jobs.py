"""Jobs: one simulation = one operating-system process.

The agent process must never carry a simulation itself.  A 1.2 s assembly run costs minutes
and, under the legacy default configuration, ends in ``SimulationFailure``; if that happened
in-process it would take the agent's state down with it, and a caller could not tell a crash
from a rejection.  So ``submit_run`` either runs the CLI in a child process and waits (short
jobs) or detaches one and hands back a handle (long jobs), and the child records its own
outcome in ``state.json`` so the job is still traceable after the agent exits.

Status is derived from the files, never from a progress counter:

    state.json.status      author\'s view: queued -> running -> finished
    manifest.json present  the run wrote its artifacts
    exit code              the CLI\'s verdict

``gate_failed`` is the fourth case the CLI cannot express: the run completed and wrote a
manifest, but ``result_status != "numerically_checked"``.  Its artifacts are readable and
must not be cited as a validated result.
"""

from __future__ import annotations

import json
import os
import random
import signal
import string
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .cases import materialise_case, sha256_file
from .core import (
    AgentError,
    ErrorCode,
    agent_home,
    predict_wall_s,
    repository_root,
    within_allowed,
)

#: Above this the call returns a handle instead of a result: a tool call that blocks for ten
#: minutes is indistinguishable from a hang.
SYNC_LIMIT_S = 60.0
DEFAULT_BUDGET_S = 900.0

_ALPHABET = string.ascii_lowercase + string.digits


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _new_job_id() -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = "".join(random.choice(_ALPHABET) for _ in range(4))
    return f"j{stamp}-{suffix}"


def _job_root() -> Path:
    root = agent_home() / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _job_dir(job_id: str) -> Path:
    if not job_id or any(character in job_id for character in "\\/.."):
        raise AgentError(ErrorCode.INVALID_ARGUMENT, f"invalid job id: {job_id!r}")
    path = _job_root() / job_id
    if not path.is_dir():
        raise AgentError(ErrorCode.JOB_NOT_FOUND, f"no such job: {job_id}")
    return path


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _environment() -> dict[str, str]:
    """Python must find ``velch`` whether or not the package is installed in site-packages."""
    env = dict(os.environ)
    source = str(repository_root() / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = source + (os.pathsep + existing if existing else "")
    env["PYTHONUTF8"] = "1"
    return env


def _program(case_path: Path, output_dir: Path, workers: int) -> list[str]:
    return [sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(case_path),
            "--output", str(output_dir), "--workers", str(int(workers))]


def _worker_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def _idempotency_key(case_sha: str, workers: int, program: list[str]) -> str:
    import hashlib

    payload = json.dumps({"case": case_sha, "workers": int(workers), "program": program,
                          "python": sys.version.split()[0]}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _status_of(job_dir: Path) -> dict[str, Any]:
    """Reconcile the three sources of truth into one status."""
    job = _read_json(job_dir / "job.json") or {}
    state = _read_json(job_dir / "state.json") or {}
    manifest_path = Path(job.get("output_dir", job_dir / "out")) / "manifest.json"
    manifest = _read_json(manifest_path)

    status = state.get("status", "queued")
    if status == "running" and not _worker_alive(state.get("pid")):
        # The child vanished without writing a verdict.  It may have been killed, or the
        # machine may have gone down; either way this job will never produce a result.
        status = "abandoned"
    if manifest is not None and status in {"finished", "running", "abandoned"}:
        summary = manifest.get("summary") or {}
        status = ("succeeded" if summary.get("result_status") == "numerically_checked"
                  else "gate_failed")
    return {
        "job_id": job.get("job_id", job_dir.name),
        "status": status,
        "output_dir": str(Path(job.get("output_dir", job_dir / "out"))),
        "case_sha256": job.get("case_sha256"),
        "workers": job.get("workers"),
        "created": job.get("created"),
        "started": state.get("started"),
        "finished": state.get("finished"),
        "exit_code": state.get("exit_code"),
        "estimate": job.get("estimate"),
        "manifest": str(manifest_path) if manifest is not None else None,
        "result_status": (manifest or {}).get("summary", {}).get("result_status"),
        "error": state.get("error"),
        "log": state.get("log"),
    }


def submit_run(*, case_path: str | Path, workers: int = 1,
               budget_s: float = DEFAULT_BUDGET_S,
               background: bool | None = None) -> dict[str, Any]:
    """Run one case.  Short jobs return their result; long ones return a handle."""
    workers = int(workers)
    if workers < 1 or workers > 64:
        raise AgentError(ErrorCode.INVALID_ARGUMENT, "workers must be between 1 and 64")
    probe = materialise_case(case_path, agent_home() / "variants" / "_probe.json")
    raw_run = json.loads(Path(probe["path"]).read_text(encoding="utf-8")).get("run", {})
    estimate = predict_wall_s(raw_run.get("duration_s", 0.0),
                             raw_run.get("output_step_s", 5e-4),
                             raw_run.get("method", "DOP853"))
    if estimate["point"] > float(budget_s):
        raise AgentError(ErrorCode.BUDGET_EXCEEDED,
                         f"estimated {estimate['point']:.0f} s exceeds the {budget_s:.0f} s budget",
                         estimate=estimate, budget_s=float(budget_s))

    job_id = _new_job_id()
    job_dir = _job_root() / job_id
    output_dir = job_dir / "out"
    case_copy = materialise_case(case_path, job_dir / "case.json")
    program = _program(Path(case_copy["path"]), output_dir, workers)
    key = _idempotency_key(case_copy["sha256"], workers, program)

    for existing in sorted(_job_root().iterdir()):
        if not existing.is_dir():
            continue
        other = _read_json(existing / "job.json") or {}
        if other.get("idempotency_key") != key:
            continue
        status = _status_of(existing)["status"]
        if status in {"queued", "running", "succeeded", "gate_failed"}:
            return {**_status_of(existing), "reused": True}

    job = {
        "job_id": job_id, "created": _now(), "case": str(Path(case_path)), "case_sha256": case_copy["sha256"],
        "case_snapshot": case_copy["path"], "output_dir": str(output_dir), "workers": workers,
        "program": program, "idempotency_key": key, "estimate": estimate,
    }
    _write_json(job_dir / "job.json", job)
    log_path = job_dir / "worker.log"
    state = {"status": "queued", "created": _now(), "log": str(log_path)}
    _write_json(job_dir / "state.json", state)

    run_inline = (estimate["point"] <= SYNC_LIMIT_S) if background is None else not background
    if run_inline:
        state["status"] = "running"
        state["started"] = _now()
        state["pid"] = os.getpid()
        _write_json(job_dir / "state.json", state)
        with log_path.open("w", encoding="utf-8", newline="\n") as log:
            completed = subprocess.run(program, cwd=str(repository_root()), env=_environment(),
                                       stdout=log, stderr=subprocess.STDOUT, check=False)
        state.update({"status": "finished", "finished": _now(), "exit_code": completed.returncode,
                      "pid": None})
        _write_json(job_dir / "state.json", state)
        return {**_status_of(job_dir), "inline": True}

    detach = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    with log_path.open("w", encoding="utf-8", newline="\n") as log:
        child = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-m", "velch.agent.worker", str(job_dir)],
            cwd=str(repository_root()), env=_environment(), stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, creationflags=detach if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
    state.update({"status": "running", "started": _now(), "pid": child.pid})
    _write_json(job_dir / "state.json", state)
    return {**_status_of(job_dir), "inline": False, "pid": child.pid}


def job_status(job_id: str) -> dict[str, Any]:
    return _status_of(_job_dir(job_id))


def list_jobs(*, limit: int = 20) -> dict[str, Any]:
    entries = []
    for path in sorted(_job_root().iterdir(), reverse=True)[: max(0, int(limit))]:
        if path.is_dir():
            entries.append(_status_of(path))
    return {"count": len(entries), "jobs": entries}


def cancel_job(job_id: str) -> dict[str, Any]:
    """Stop a job that is still running.  A finished job is reported, not rewritten."""
    directory = _job_dir(job_id)
    state = _read_json(directory / "state.json") or {}
    pid = state.get("pid")
    if state.get("status") != "running" or not _worker_alive(pid):
        return {**_status_of(directory), "cancelled": False,
                "reason": "job is not running"}
    try:
        os.kill(int(pid), signal.SIGTERM)
    except OSError as error:
        raise AgentError(ErrorCode.SOLVER_ERROR, f"could not stop pid {pid}: {error}") from error
    state.update({"status": "cancelled", "finished": _now(), "error": "cancelled by caller"})
    _write_json(directory / "state.json", state)
    return {**_status_of(directory), "cancelled": True}


def read_result(job_id: str) -> dict[str, Any]:
    """Artifacts of a finished job.  Fail closed when the manifest is missing.

    A ``history.csv`` without a ``manifest.json`` is exactly what an interrupted save leaves
    behind, and it is indistinguishable from a complete one by looking at the CSV alone.
    """
    directory = _job_dir(job_id)
    status = _status_of(directory)
    if status["manifest"] is None:
        if status["status"] in {"running", "queued"}:
            raise AgentError(ErrorCode.JOB_NOT_FINISHED, f"job {job_id} is {status['status']}",
                             job=status)
        raise AgentError(ErrorCode.ARTIFACT_INTEGRITY,
                         f"job {job_id} has no manifest.json; its history.csv cannot be trusted",
                         job=status)
    manifest_path = Path(status["manifest"])
    manifest = _read_json(manifest_path) or {}
    history = manifest_path.parent / "history.csv"
    if not history.exists():
        raise AgentError(ErrorCode.ARTIFACT_INTEGRITY,
                         f"manifest lists a run but {history} is missing", job=status)
    summary = manifest.get("summary") or {}
    return {
        "job_id": status["job_id"],
        "status": status["status"],
        "result_status": summary.get("result_status"),
        "physics_validation_status": summary.get("physics_validation_status"),
        "summary": summary,
        "artifacts": {
            "history": str(history),
            "history_sha256": sha256_file(history),
            "manifest": str(manifest_path),
            "case_snapshot": manifest.get("case_snapshot"),
        },
        "quotable": summary.get("result_status") == "numerically_checked",
        "note": "" if summary.get("result_status") == "numerically_checked" else
                "The run completed but its numerical gates did not all pass; read it, do not cite it.",
    }
