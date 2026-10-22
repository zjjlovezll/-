"""A1: does a bounded strip patch change the frog contact loss?

``find_strip_contact`` integrates over the whole wheel/rail overlap, so a
flangeway recess or a seat cut contributes to the normal force and pulls the
reported contact point sideways.  ``strip_half_width_m`` bounds that integration;
``strip_center_policy`` decides where the patch sits:

* ``deepest``   -- bootstrap on the hardest-pressed strip (what the unbounded form
                   implicitly does, so this isolates the *width* effect);
* ``reference`` -- centre on the rail reference plane, i.e. the crown datum.

Reference point: ``case_frog_N_strip05`` peaks at 170.860 kN with 10 of 101
samples at zero load.

Usage::

    python -X utf8 ab_strip_window.py [duration_s]
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
REPO = BASE.parent.parent
PY = sys.executable
COLUMN = "axle1_right_normal_n"
DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 0.05

VARIANTS: tuple[tuple[str, float | None, str], ...] = (
    ("base", None, "deepest"),
    ("h5", 0.005, "deepest"),
    ("run", None, "run"),
)


def build(name: str, half: float | None, policy: str) -> tuple[str, Path]:
    case = json.loads((BASE / "case_frog_N_strip05.json").read_text(encoding="utf-8"))
    contact = case["contact"]
    if contact.get("normal_policy") != "strip_integral":
        raise SystemExit(f"case is not strip_integral: {contact.get('normal_policy')!r}")
    if half is None:
        contact.pop("strip_half_width_m", None)
        contact.pop("strip_center_policy", None)
    else:
        contact["strip_half_width_m"] = half
        contact["strip_center_policy"] = policy
    case["run"]["duration_s"] = DURATION
    case_id = f"a1_{name}"
    case["case_id"] = case_id
    path = BASE / f"case_{case_id}.json"
    path.write_text(json.dumps(case, indent=2), encoding="utf-8")
    return case_id, path


def run(case_id: str, path: Path) -> dict:
    output = BASE / f"out_{case_id}"
    started = time.perf_counter()
    proc = subprocess.run(
        [PY, "-m", "velch", "run-vehicle", str(path), "--output", str(output)],
        cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace",
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
        "peak_kn": float(force.max()) / 1e3,
        "min_kn": float(force.min()) / 1e3,
        "zero_samples": int(np.count_nonzero(force <= 1.0)),
        "gates_pass": bool(all(summary["gates"].values())),
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"case_frog_N_strip05, {DURATION} s window, reference peak 170.860 kN / 10 zero")
    print(f"{'variant':14s} {'peak kN':>9s} {'min kN':>8s} {'zero':>5s} {'nfev':>7s} {'wall s':>7s}  gates")
    results: list[dict] = []
    for name, half, policy in VARIANTS:
        case_id, path = build(name, half, policy)
        record = run(case_id, path)
        results.append(record)
        if "error" in record:
            print(f"{name:14s} FAILED after {record['wall_s']:.1f} s")
            print(record["error"])
            continue
        print(
            f"{name:14s} {record['peak_kn']:9.3f} {record['min_kn']:8.3f}"
            f" {record['zero_samples']:5d} {record['nfev']:7d} {record['wall_s']:7.1f}"
            f"  {record['gates_pass']}"
        )
    (BASE / "strip_window_a1.json").write_text(
        json.dumps({"duration_s": DURATION, "runs": results}, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
