"""Rebuild the 18-turnout diverging case on one design line (B041).

The case's two sides come from two different models:

* ``left``  -- ``Profile_Mileage_JBG.prr`` (CRH380A rigid model), 19 001 stations, 30-125 m
* ``right`` -- ``jbg-20200418-R.prr`` (SDITT), 16 664 stations, 30-116.59 m

Each carries its own ``y_offset_m`` progression, so the pair does not describe one track.  Measured
rail-centre offsets (before this fix):

| s (m) | left offset | shift vs base | right offset | shift vs base | gauge   |
|-------|-------------|---------------|--------------|---------------|---------|
| 60    | -0.71267    | +0.04033      | +0.73116     | -0.02167      | 1.44383 |
| 69    | -0.59884    | +0.15416      | +0.90910     | +0.15627      | 1.50794 |
| 79    | -0.38605    | +0.36695      | +1.18342     | +0.43059      | 1.56947 |
| 84    | -0.24559    | +0.50741      | +1.34204     | +0.58921      | 1.58763 |
| 94    | +0.10347    | +0.85647      | +1.65928     | +0.90645      | 1.55581 |

The left side follows the design line ``y = s^2 / (2 * 1100.75)`` to 1e-4 (shift column equals
``path.at``); the right side drifts up to +64 mm off it.  Consequently the gauge wanders between
1.444 m and 1.588 m while the wheels are placed at ``2 * 0.7465 = 1.493 m``, and at 79-94 m the right
wheel rides the gauge corner: seated first frame gives ``axle3_right 160.5 kN = 2.69x`` share with
120.6 um penetration while ``axle1_right`` and ``axle2_right`` find no contact at all.

The fix keeps the left side as the reference (it *is* the design line) and rewrites each right station
offset to ``left(s) + 1.493``.  The right profile **shape** file is untouched -- only where its centre
sits.  That is also what Simpack's TRACK does: the line type fixes the reference line and the gauge,
the profile is expressed relative to its own rail centre.

Run:  python -X utf8 scripts/s30_fix_diverging_gauge.py [--gauge 1.493]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from velch import data_root

CASE = "case_diverging_R1100.json"


def offsets(stations: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    s = np.asarray([float(st["s_m"]) for st in stations], dtype=float)
    y = np.asarray([float(st["profile"]["y_offset_m"]) for st in stations], dtype=float)
    return s, y


def report(left_s: np.ndarray, left_y: np.ndarray, right_s: np.ndarray, right_y: np.ndarray) -> None:
    print(f"{'s (m)':>7s} {'left y':>10s} {'right y':>10s} {'gauge':>9s} {'asym (mm)':>10s} "
          f"{'path.at':>9s}")
    for s in (60.0, 69.0, 79.0, 84.0, 89.0, 94.0, 100.0):
        ly = float(np.interp(s, left_s, left_y))
        ry = float(np.interp(s, right_s, right_y))
        print(f"{s:7.1f} {ly:+10.5f} {ry:+10.5f} {ry - ly:9.5f} "
              f"{((ry - ly) / 2 - 0.7465) * 1e3:+10.2f} {max(s - 50.578, 0.0) ** 2 / 2201.5:9.5f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gauge", type=float, default=1.493,
                        help="rail-centre distance to impose (default: 2 * 0.7465 = 1.493 m)")
    options = parser.parse_args()

    source = data_root.case_dir() / CASE
    raw = json.loads(source.read_text(encoding="utf-8"))
    templates = {t["id"]: t for t in raw["rail_templates"]}
    left_s, left_y = offsets(templates["left"]["stations"])
    right_s, right_y = offsets(templates["right"]["stations"])

    print("=== before ===")
    report(left_s, left_y, right_s, right_y)
    before = right_y - np.interp(right_s, left_s, left_y)
    print(f"right offset relative to left: min {before.min():+.5f} max {before.max():+.5f} m")

    for station in templates["right"]["stations"]:
        s = float(station["s_m"])
        if s < left_s[0] or s > left_s[-1]:
            continue
        # The left table IS the design line (its offsets reproduce y = s^2/(2R) to 1e-4) and its
        # centre already sits at -0.753 m, so the right centre is left + gauge, not left + gauge/2.
        station["profile"]["y_offset_m"] = float(np.interp(s, left_s, left_y)) + options.gauge

    right_s2, right_y2 = offsets(templates["right"]["stations"])
    print("\n=== after ===")
    report(left_s, left_y, right_s2, right_y2)
    after = right_y2 - np.interp(right_s2, left_s, left_y)
    print(f"right offset relative to left: min {after.min():+.5f} max {after.max():+.5f} m")
    print(f"stations outside the left table (left untouched): "
          f"{int(np.count_nonzero((right_s2 < left_s[0]) | (right_s2 > left_s[-1])))}")

    raw["case_id"] = f"{raw.get('case_id', 'diverging')}_gauge{options.gauge:.3f}"
    raw.setdefault("purpose_detail", "")
    raw["purpose_detail"] = (str(raw["purpose_detail"]) +
                             f" [B041: right rail centre rebuilt on the left rail's design line at a "
                             f"{options.gauge:.3f} m gauge; the two sides previously came from different "
                             f"models and the gauge wandered 1.444-1.588 m]").strip()
    target = Path(__file__).resolve().parents[2] / "scratch" / "s30" / "case_diverging_gauge.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    print(f"\nwrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
