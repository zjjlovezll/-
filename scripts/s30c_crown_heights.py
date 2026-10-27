"""Rail crown height/height difference between the two sides of the rebuilt diverging case.

The gauge rebuild fixed the lateral geometry (gauge exactly 1.493 m at every station) but the seated
vertical equilibrium then stopped converging.  A z-only seat cannot absorb a *height* difference
between the two rails, so this prints the crown heights the contact actually sees.

Run:  python -X utf8 scripts/s30c_crown_heights.py [--case PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics

STATIONS_M = (45.0, 55.0, 59.0, 61.5, 69.0, 76.5, 79.0, 83.6, 89.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default=None,
                        help="case JSON; default is the original corpus case")
    options = parser.parse_args()
    if options.case is None:
        raw = json.loads((data_root.case_dir() / "case_diverging_R1100.json").read_text(encoding="utf-8"))
        target = Path(__file__).resolve().parents[2] / "scratch" / "s30" / "case_heights.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    else:
        target = Path(options.case)

    case = load_vehicle_case(target)
    dynamics = VehicleDynamics(case)
    zeros = np.zeros(dynamics.dimension)
    print(f"case {target.name}")
    print(f"{'s (m)':>7s} {'left y':>9s} {'right y':>9s} {'gauge':>8s} "
          f"{'left z':>10s} {'right z':>10s} {'dz (um)':>9s}")
    for index, rail in enumerate(case.rails):
        del index
        if not str(rail.id).endswith("_left"):
            continue
        right = next(r for r in case.rails
                     if str(r.id) == str(rail.id).replace("_left", "_right"))
        for s in STATIONS_M:
            left_sample = rail.bodies[0].series.sample(s, 1.0)
            right_sample = right.bodies[0].series.sample(s, 1.0)
            left_y = float(np.mean(left_sample.profile.y_m))
            right_y = float(np.mean(right_sample.profile.y_m))
            left_z = float(np.max(left_sample.profile.z_m))
            right_z = float(np.max(right_sample.profile.z_m))
            print(f"{s:7.1f} {left_y:+9.5f} {right_y:+9.5f} {right_y - left_y:8.5f} "
                  f"{left_z:+10.6f} {right_z:+10.6f} {(right_z - left_z) * 1e6:9.2f}")
        break
    del zeros
    return 0


if __name__ == "__main__":
    sys.exit(main())
