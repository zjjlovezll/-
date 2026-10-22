"""Compare body-attribution runs on the frog window (plan A).

Reads each run directory's ``manifest.json`` and ``history.csv`` and prints the
right-rail load statistics of the leading axle, which is the quantity the
plan-A question is about: does the 596 kN spike fall to the Simpack 40-100 kN
band once a head outside the tread band can no longer take the load?

Usage: python cmp_attr.py <out-dir> [<out-dir> ...]
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np


def load(run_dir: Path):
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = manifest.get("summary", {})
    with (run_dir / "history.csv").open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    time = np.array([float(r["time_s"]) for r in rows])
    right = np.array([float(r["axle1_right_normal_n"]) for r in rows])
    left = np.array([float(r["axle1_left_normal_n"]) for r in rows])
    pen = np.array([float(r["axle1_right_penetration_m"]) for r in rows])
    x = np.array([float(r["axle1_x_m"]) for r in rows])
    return manifest, summary, time, x, right, left, pen


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    print(f"{'run':28s} {'status':22s} {'right peak':>11s} {'mean':>9s} {'min':>9s} "
          f"{'off':>5s} {'maxpen mm':>9s} {'nfev':>8s}")
    for name in argv[1:]:
        run_dir = Path(name)
        manifest, summary, time, x, right, left, pen = load(run_dir)
        status = summary.get("result_status", "?")
        off = int(np.count_nonzero(right <= 0.0))
        print(f"{run_dir.name:28s} {status:22s} {right.max():11.0f} {right.mean():9.0f} "
              f"{right.min():9.0f} {off:5d} {pen.max() * 1e3:9.3f} "
              f"{summary.get('nfev', 0):8d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
