"""Child-process entry point for one detached job.

The agent starts this module and forgets about it; this process runs the CLI, records the
exit code and its own timestamps in ``state.json``, and then exits.  If it is killed before
that, ``state.json`` keeps ``status: running`` with a dead pid, and the job layer reads that
as ``abandoned`` rather than pretending the run is still going.

Kept dependency-free (standard library only) on purpose: it must still be able to record a
failure when importing ``velch`` is what went wrong.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _write(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m velch.agent.worker <job-dir>", file=sys.stderr)
        return 2
    job_dir = Path(argv[0]).resolve()
    job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    state_path = job_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    state.update({"status": "running", "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                  "pid": os.getpid()})
    _write(state_path, state)
    try:
        completed = subprocess.run(job["program"], cwd=str(job_dir), check=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        exit_code, error = int(completed.returncode), None
    except OSError as failure:  # the interpreter or the module is missing: still a verdict
        exit_code, error = -1, f"{type(failure).__name__}: {failure}"
    state.update({"status": "finished", "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
                  "exit_code": exit_code, "pid": None, "error": error})
    _write(state_path, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
