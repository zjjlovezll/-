"""Micro-benchmark the Velch vehicle RHS hot path on the real CRH380A_M case.

Measures, per call, the two NumPy-heavy operations that run for every rail
patch inside every RHS evaluation:

  * ProfileSeries.sample   - longitudinal interpolation between PRR stations
  * find_graph_contact     - wheel/rail lower-envelope search

and reports how many of each the full 1.2 s run performs, so the measured
per-call cost can be projected onto the recorded 354.5 s wall time.
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path

from velch.contact import find_graph_contact
from velch.vehicle import load_vehicle_case

CASE = Path("validation/crh380a_m/case_B_turnout.json")
REPEATS = 2000
SANK_WHEEL_Z_M = 0.43 - 0.000463


def timed(fn, repeats: int) -> tuple[float, float]:
    samples = []
    for _ in range(5):
        t0 = time.perf_counter()
        for _ in range(repeats):
            fn()
        samples.append((time.perf_counter() - t0) / repeats)
    return statistics.median(samples), min(samples)


def main() -> None:
    case = load_vehicle_case(CASE)
    rails = case.rails
    print(f"rails per model         : {len(rails)} (each axle expands a template)")
    print(f"rail 0 id               : {rails[0].id}")
    print(f"track kind              : {case.track_kind}")

    rail = rails[0]
    wheel = {item.id: item for item in case.wheels}[rail.wheel_id]
    x_m = 23.5  # front axle at t = 0 for x_start = 13.5 m

    sample = rail.profiles.sample(x_m, 1)
    print(f"profile points per side : wheel={wheel.profile.y_m.size}  rail={sample.profile.y_m.size}")

    def sample_call() -> None:
        rail.profiles.sample(x_m, 1)

    def contact_call() -> None:
        find_graph_contact(
            wheel.profile,
            sample,
            wheel_y_m=0.0,
            wheel_z_m=SANK_WHEEL_Z_M,
            wheel_roll_rad=0.0,
            wheel_lateral_offset_m=wheel.lateral_offset_m,
            rail_y_m=0.0,
            rail_z_m=0.0,
        )

    median_sample, best_sample = timed(sample_call, REPEATS)
    median_contact, best_contact = timed(contact_call, REPEATS)

    geometry = find_graph_contact(
        wheel.profile,
        sample,
        wheel_y_m=0.0,
        wheel_z_m=SANK_WHEEL_Z_M,
        wheel_roll_rad=0.0,
        wheel_lateral_offset_m=wheel.lateral_offset_m,
        rail_y_m=0.0,
        rail_z_m=0.0,
    )
    print()
    print(f"ProfileSeries.sample    : median {median_sample * 1e6:8.1f} us   best {best_sample * 1e6:8.1f} us")
    print(f"find_graph_contact      : median {median_contact * 1e6:8.1f} us   best {best_contact * 1e6:8.1f} us")
    if geometry is not None:
        print(f"  sample geometry       : penetration={geometry.penetration_m * 1e3:.4f} mm "
              f"y={geometry.y_m * 1e3:.3f} mm  edge_limited={geometry.edge_limited}")

    per_patch = median_sample + median_contact
    per_rhs = per_patch * len(rails)
    print()
    print(f"contact+sample per patch: {per_patch * 1e6:8.1f} us")
    print(f"projected per RHS       : {per_rhs * 1e6:8.1f} us  ({len(rails)} patches)")
    for label, nfev, wall in (("case B 1.2 s", 233909, 354.5), ("case A 1.2 s", 151217, 209.6)):
        projected = per_rhs * nfev
        print(f"{label:14s} : nfev={nfev:7d}  projected {projected:7.1f} s "
              f"= {100.0 * projected / wall:5.1f} % of the {wall:.1f} s measured wall time")


if __name__ == "__main__":
    main()
