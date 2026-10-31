"""Run several cases at once, without letting them corrupt the archive index.

Why this exists: nothing in the solver is serial by construction -- one run is one independent process -- but the
only thing I had been doing was launching them back to back, because every run appends to a single
``scratch/runs/index.jsonl`` with a read-modify-write.  Two runs finishing at the same moment could lose a line.

So this script does the two things a batch needs:

1. **a cross-process lock around the index write only** (``s99_run_archive.write_index`` takes the lock when
   ``VELCH_INDEX_LOCK=1``), so the simulations really do overlap and only the bookkeeping is serialised;
2. **one worker per core, each pinned to one BLAS thread** (``OMP_NUM_THREADS=1`` and friends), because numpy's
   default is to spawn as many threads as cores *per process* -- eight workers x eight threads would fight.

Resume is free: a run whose ``run_id`` is already in the index is skipped, so an interrupted batch can be
restarted with the same command line.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))

import s99_run_archive as archive  # noqa: E402

ROOT = HERE.parents[1]
SCRATCH = ROOT.parent / "scratch"
LOG_DIR = SCRATCH / "campaign_logs"


def indexed() -> set[str]:
    if not archive.INDEX.exists():
        return set()
    found = set()
    for line in archive.INDEX.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            found.add(str(json.loads(line)["run_id"]))
        except (json.JSONDecodeError, KeyError):
            continue
    return found


def planned(cases: list[pathlib.Path], speed_kmh: float, duration_s: float, output_step_s: float,
            notes: dict[str, str]) -> list[dict]:
    """One dict per (case, speed) with the exact command and the run_id it will produce."""
    jobs = []
    for case in cases:
        path, route = archive.resolve_case("straight", str(case))
        digest = archive.sha256_of(path)
        run_id = archive.run_id_for(route, speed_kmh, duration_s, output_step_s, digest)
        jobs.append({"case": path, "route": route, "run_id": run_id, "speed_kmh": speed_kmh,
                     "duration_s": duration_s, "output_step_s": output_step_s, "notes": dict(notes)})
    return jobs


def command(job: dict) -> list[str]:
    argv = [sys.executable, "-X", "utf8", str(HERE.parent / "s99_run_archive.py"),
            "--case", str(job["case"]), "--speed-kmh", f"{job['speed_kmh']:.0f}",
            "--duration", f"{job['duration_s']:.4f}", "--output-step", f"{job['output_step_s']:.6g}"]
    for key, value in job["notes"].items():
        argv += ["--note", f"{key}={value}"]
    return argv


def worker_environment() -> dict[str, str]:
    env = dict(os.environ)
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[name] = "1"
    env["VELCH_INDEX_LOCK"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_one(job: dict, env: dict[str, str]) -> dict:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{job['run_id']}.log"
    started = time.time()
    with log_path.open("w", encoding="utf-8") as log:
        log.write(" ".join(command(job)) + "\n")
        log.flush()
        finished = subprocess.run(command(job), stdout=log, stderr=subprocess.STDOUT, env=env, text=True)
    return {"run_id": job["run_id"], "returncode": finished.returncode,
            "wall_s": round(time.time() - started, 1), "log": str(log_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="run several cases concurrently")
    parser.add_argument("--case", action="append", required=True, help="case path, repeatable")
    parser.add_argument("--speed-kmh", type=float, required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--output-step", type=float, default=5e-4)
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--note", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--force", action="store_true", help="re-run even if the run_id is indexed")
    args = parser.parse_args()

    notes = {}
    for item in args.note:
        if "=" not in item:
            parser.error(f"--note needs KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        notes[key] = value
    notes.setdefault("campaign", "parallel")

    jobs = planned([pathlib.Path(item) for item in args.case], args.speed_kmh, args.duration,
                   args.output_step, notes)
    done = indexed()
    pending = [job for job in jobs if args.force or job["run_id"] not in done]
    for job in jobs:
        state = "run" if job in pending else "skip (already indexed)"
        print(f"{job['run_id']}  {state}")
    if args.dry or not pending:
        print(f"{len(pending)} to run, {len(jobs) - len(pending)} skipped, jobs={args.jobs}")
        return 0

    env = worker_environment()
    print(f"launching {len(pending)} run(s) on {min(args.jobs, len(pending))} worker(s)")
    results = []
    started = time.time()
    with futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        submitted = [pool.submit(run_one, job, env) for job in pending]
        for finished in futures.as_completed(submitted):
            result = finished.result()
            results.append(result)
            print(f"  {result['run_id']}  exit {result['returncode']}  {result['wall_s']} s")
    total = time.time() - started
    serial = sum(item["wall_s"] for item in results)
    failures = [item for item in results if item["returncode"] != 0]
    print(f"finished {len(results)} run(s) in {total:.1f} s wall; serial sum {serial:.1f} s")
    if failures:
        for item in failures:
            print(f"FAILED {item['run_id']} -> {item['log']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
