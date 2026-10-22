"""Compare a flat-section run with and without 1:40 rail cant."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def load(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    summary = manifest["summary"]
    rows = list(csv.DictReader((directory / "history.csv").open(encoding="utf-8")))
    right = [float(r["axle1_right_normal_n"]) for r in rows]
    left = [float(r["axle1_left_normal_n"]) for r in rows]
    z = [float(r["axle1_z_m"]) for r in rows]
    y = [float(r["axle1_y_m"]) for r in rows]
    return {
        "name": directory.name,
        "peak_right": max(right),
        "peak_left": max(left),
        "min_right": min(right),
        "mean_right": sum(right) / len(right),
        "z_pp": (max(z) - min(z)) * 1e3,
        "y_pp": (max(y) - min(y)) * 1e3,
        "lost": summary.get("contact_lost_samples", 0),
        "max_pen": summary.get("max_penetration_m", 0.0),
        "max_hertz": summary.get("max_hertz_penetration_m", 0.0),
        "static": summary.get("residuals", {}).get("vertical_preload_n", 0.0),
    }


def main() -> int:
    directories = [Path(p) for p in sys.argv[1:]]
    if len(directories) < 2:
        raise SystemExit("usage: cmp_cant.py <dir_ref> <dir_cant> [...]")
    results = [load(d) for d in directories]
    header = (f"{'run':<28} {'P_R pk kN':>10} {'P_R mn kN':>10} {'P_R mean':>9} "
              f"{'z pp mm':>8} {'y pp mm':>8} {'pen mm':>8}")
    print(header)
    for r in results:
        print(f"{r['name']:<28} {r['peak_right']/1e3:>10.2f} {r['min_right']/1e3:>10.2f} "
              f"{r['mean_right']/1e3:>9.2f} {r['z_pp']:>8.4f} {r['y_pp']:>8.4f} "
              f"{r['max_hertz']*1e3:>8.4f}")
    reference = results[0]
    print()
    for r in results[1:]:
        delta = (r["peak_right"] - reference["peak_right"]) / reference["peak_right"] * 100.0
        dmean = (r["mean_right"] - reference["mean_right"]) / reference["mean_right"] * 100.0
        print(f"{r['name']}: peak {delta:+.2f}%  mean {dmean:+.3f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
