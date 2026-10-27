"""Round 37: measure the wheel-vs-rail height under +roll, inside _absolute_arrays."""

import sys

import numpy as np

sys.path.insert(0, r"F:\ai閬撳矓鐘舵€佸弽婕旇鲸璇哱Velch\src")

from velch.contact_search import _absolute_arrays
from velch.vehicle import load_vehicle_case

CASE = r"F:\velch_tmp\curve34\case_R1100_cantM107_100.json"


def main() -> int:
    case = load_vehicle_case(CASE)
    rail = case.rails[0]
    bodies = getattr(rail, "contact_bodies", None) or getattr(rail, "bodies", None)
    series = bodies[0].series if bodies else rail.profiles
    sample = series.sample(70.0, 1)
    wheel = case.wheels[0]

    print(f"case: {case.case_id}, rail {rail.id}, wheel {wheel.id}")
    print(f"wheel profile y range {wheel.profile.y_m[0]:+.5f}..{wheel.profile.y_m[-1]:+.5f}")

    for roll, label in ((0.0, "roll 0"), (0.071729, "roll +"), (-0.071729, "roll -")):
        wheel_y, wheel_z, rail_y, rail_z = _absolute_arrays(
            wheel_profile=wheel.profile,
            wheel_y_m=0.0,
            wheel_z_m=0.43,
            wheel_roll_rad=roll,
            wheel_lateral_offset_m=wheel.lateral_offset_m,
            rail_y_m=0.0,
            rail_z_m=0.0,
            rail_sample=sample,
        )
        lo = max(wheel_y.min(), rail_y.min())
        hi = min(wheel_y.max(), rail_y.max())
        grid = np.linspace(lo, hi, 4001)
        wz = np.interp(grid, wheel_y, wheel_z)
        rz = np.interp(grid, rail_y, rail_z)
        gap = rz - wz
        index = int(np.argmax(gap))
        print(f"  {label}: min gap {gap.min() * 1e3:+8.3f} mm at y {grid[int(np.argmin(gap))]:+.4f}; "
              f"max gap {gap.max() * 1e3:+8.3f} mm at y {grid[index]:+.4f}; "
              f"wheel z at wheel centre {wheel_z[np.argmin(np.abs(wheel_y))] * 1e3:.3f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
