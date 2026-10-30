"""Where does each rail's crown sit, and where is the wheel plane?

Rounds 222-223 rebuilt the rigid straight case's right rail as the through route by cloning one station's
``y_offset_m`` over the whole table.  Every offset difference in 1.4796..1.5065 m then failed to seat, so
the offset was not the controlling quantity.  This measures instead of guessing: for each rail it finds
the crown (the highest point of its own sampled profile) in absolute lateral coordinates, and compares it
with the plane each wheel is standing in.  A wheel must touch its rail near the crown, not on a flank.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--mileage", type=float, default=40.0)
    options = parser.parse_args()

    case = load_vehicle_case(options.case)
    print(f"case {options.case.name}  x_start {case.run.x_start_m:.1f} m  "
          f"speed {case.vehicle.travel_speed_m_s * 3.6:.1f} km/h  rails {len(case.rails)}")
    print(f"wheel lateral offsets: {[round(wheel.lateral_offset_m, 4) for wheel in case.wheels]}")
    for rail in case.rails:
        # ``ProfileSample.profile.y_m`` is already an absolute lateral coordinate (offset folded in).
        profile = rail.bodies[0].series.sample(options.mileage, 1.0).profile
        crown = int(np.argmax(profile.z_m))
        print(
            f"  {rail.id:<14} crown {float(profile.y_m[crown]):+.6f} m"
            f"  z {float(profile.z_m[crown]) * 1e3:+.3f} mm  span "
            f"{float(profile.y_m[0]) * 1e3:+.1f}..{float(profile.y_m[-1]) * 1e3:+.1f} mm  points {profile.y_m.size}"
        )
    left = next(rail for rail in case.rails if rail.id.endswith("_left"))
    right = next(rail for rail in case.rails if rail.id.endswith("_right"))
    left_profile = left.bodies[0].series.sample(options.mileage, 1.0).profile
    right_profile = right.bodies[0].series.sample(options.mileage, 1.0).profile
    left_crown = float(left_profile.y_m[int(np.argmax(left_profile.z_m))])
    right_crown = float(right_profile.y_m[int(np.argmax(right_profile.z_m))])
    print(f"  crown to crown: {right_crown - left_crown:+.6f} m  "
          f"(wheel planes are {2 * abs(case.wheels[0].lateral_offset_m):+.6f} m apart)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
