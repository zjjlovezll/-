"""B1 probe: does ``max_solver_step_s`` bind the step count?

The flat rigid case carries ``max_solver_step_s = 1e-4`` while the full
1.2 s run spends 151 217 RHS calls, i.e. ~12 600 DOP853 steps of 95 us --
about 95 % of the cap.  That arithmetic suggests the step size is set by
the cap and not by the dynamics.  This probe runs a short window with
several caps and with no cap at all, and compares nfev, wall clock and
the force trace against the tightest cap.

Usage::

    python -X utf8 probe_step_cap.py [duration_s]

Writes ``step_cap_b1.json`` next to this file.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
REPO = BASE.parent.parent  # ...\Velch
PY = sys.executable
COLUMN = "axle1_right_normal_n"

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 0.1
CASE_STEM = sys.argv[2] if len(sys.argv) > 2 else "case_A_plain"
TAG = CASE_STEM.removeprefix("case_").replace("_", "-")
REFERENCE = f"b1_{TAG}_cap1e-4"

# name, max_solver_step_s (duration_s == no cap), rtol
VARIANTS: tuple[tuple[str, float, float], ...] = (
    ("cap1e-4", 1.0e-4, 1.0e-6),
    ("cap2p5e-4", 2.5e-4, 1.0e-6),
    ("cap5e-4", 5.0e-4, 1.0e-6),
    ("cap1e-3", 1.0e-3, 1.0e-6),
    ("free", DURATION, 1.0e-6),
    ("free_rtol1e-5", DURATION, 1.0e-5),
    ("free_rtol1e-4", DURATION, 1.0e-4),
)


def build(name: str, cap: float, rtol: float) -> tuple[str, Path]:
    """Write a variant case that only changes the run block."""
    case = json.loads((BASE / f"{CASE_STEM}.json").read_text(encoding="utf-8"))
    run = case["run"]
    run["duration_s"] = DURATION
    run["max_solver_step_s"] = cap
    run["rtol"] = rtol
    case_id = f"b1_{TAG}_{name}"
    case["case_id"] = case_id
    path = BASE / f"case_{case_id}.json"
    path.write_text(json.dumps(case, indent=2), encoding="utf-8")
    return case_id, path


def run(case_id: str, path: Path) -> dict:
    """Run one case and pull nfev + the right-wheel force trace."""
    output = BASE / f"out_{case_id}"
    started = time.perf_counter()
    proc = subprocess.run(
        [PY, "-m", "velch", "run-vehicle", str(path), "--output", str(output)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    wall = time.perf_counter() - started
    if proc.returncode != 0:
        return {"case": case_id, "wall_s": wall, "error": (proc.stderr or proc.stdout)[-600:]}
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    summary = manifest["summary"]
    table = np.genfromtxt(output / "history.csv", delimiter=",", names=True)
    force = np.asarray(table[COLUMN], dtype=float)
    return {
        "case": case_id,
        "wall_s": wall,
        "nfev": int(summary["solver"]["nfev"]),
        "samples": int(force.size),
        "peak_n": float(force.max()),
        "min_n": float(force.min()),
        "rms_n": float(np.sqrt(np.mean(force**2))),
        "gates_pass": bool(all(summary["gates"].values())),
        "force": force,
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    results: list[dict] = []
    for name, cap, rtol in VARIANTS:
        case_id, path = build(name, cap, rtol)
        record = run(case_id, path)
        results.append(record)
        if "error" in record:
            print(f"{case_id:16s} FAILED in {record['wall_s']:.1f} s")
            print(record["error"])
        else:
            print(
                f"{case_id:16s} nfev {record['nfev']:7d}  wall {record['wall_s']:6.1f} s"
                f"  peak {record['peak_n'] / 1e3:8.3f} kN  min {record['min_n'] / 1e3:7.3f} kN"
            )

    reference = next((item for item in results if item["case"] == REFERENCE and "force" in item), None)
    if reference is None:
        print("reference run failed; no deltas")
        return 1

    print()
    print(f"deltas against {REFERENCE} (same output grid, {reference['samples']} samples)")
    for record in results:
        if "force" not in record:
            continue
        if record["samples"] != reference["samples"]:
            print(f"{record['case']:16s} sample mismatch")
            continue
        delta = record["force"] - reference["force"]
        speedup = reference["wall_s"] / record["wall_s"] if record["wall_s"] > 0 else float("nan")
        print(
            f"{record['case']:16s} max|dN| {np.abs(delta).max() / 1e3:8.4f} kN"
            f"  rms(dN) {np.sqrt(np.mean(delta**2)) / 1e3:8.4f} kN"
            f"  wall x{speedup:5.2f}"
        )

    payload = [
        {key: value for key, value in record.items() if key != "force"} for record in results
    ]
    (BASE / f"step_cap_b1_{TAG}.json").write_text(
        json.dumps(
            {"case": CASE_STEM, "duration_s": DURATION, "runs": payload}, indent=2
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
