"""Split one contact evaluation into its two halves.

``_absolute_arrays`` rebuilds the *whole* rotated wheel and rail surface; the strip
sum then works over a few hundred lateral points.  Timing them apart says which of
the two the 150 us per patch belongs to.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from velch import contact as contact_module           # noqa: E402
from velch.vehicle import load_vehicle_case           # noqa: E402


def main() -> int:
    case = load_vehicle_case(Path(sys.argv[1]))
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    q = np.asarray(case.initial_q, float)
    rail = case.rails[0]
    wheel = next(w for w in case.wheels if w.id == rail.wheel_id)
    body = rail.contact_bodies[0]
    x = case.run.x_start_m + case.vehicle.axle_offsets_m[rail.axle_index]
    sample = body.series.sample(x, 1)
    print(f"wheel profile points : {wheel.profile.y_m.size}")
    print(f"rail  profile points : {sample.profile.y_m.size}")
    print(f"wheel body extent    : {wheel.profile.z_m.size} z values")

    kwargs = dict(
        wheel_y_m=float(q[0]),
        wheel_z_m=case.vehicle.wheel_center_height_m + float(q[1]),
        wheel_roll_rad=float(q[2]),
        wheel_lateral_offset_m=wheel.lateral_offset_m,
        rail_y_m=0.753,
        rail_z_m=0.0,
    )
    start = time.perf_counter()
    for _ in range(repeats):
        contact_module._absolute_arrays(wheel.profile, sample, **kwargs)
    absolute_us = (time.perf_counter() - start) / repeats * 1e6

    start = time.perf_counter()
    for _ in range(repeats):
        contact_module.find_strip_contact(
            wheel.profile, sample, **kwargs,
            strip_dy_m=case.contact.strip_dy_m,
            strip_min_depth_m=case.contact.strip_min_depth_m,
            effective_modulus_pa=case.contact.effective_modulus_pa,
            effective_radius_m=case.contact.effective_radius_m,
            stiffness_policy=case.contact.stiffness_policy)
    total_us = (time.perf_counter() - start) / repeats * 1e6
    print()
    print(f"_absolute_arrays     : {absolute_us:8.1f} us  ({absolute_us / total_us * 100:5.1f}%)")
    print(f"find_strip_contact   : {total_us:8.1f} us")
    print(f"rest of strip law    : {total_us - absolute_us:8.1f} us")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
