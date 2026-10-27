"""What does the accepted curved-turnout run actually put on the rails?

Gate 6 rests on one claim from earlier rounds: the 18 turnout diverging route at 80 km/h runs
``numerically_checked`` with all eight wheels carrying load.  This script re-runs exactly that
configuration for a few milliseconds and prints, per patch, the normal force, the penetration and
the lateral position of the contact, so the claim is checked against the contact table instead of
against the gate summary.

It also prints where the rails are: for each rail, the lateral extent of the sampled cross section
at the run's first axle mileage, next to the wheel's lateral offset.  A wheelset standing 160 mm
outboard of its rail would still produce eight *keys* in the contact dictionary; only the numbers
tell them apart.

Run:  python -X utf8 scripts/s28_curve_contact_table.py [--duration 0.005]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, simulate_vehicle

SPEED_KMH = 80.0
SEAT_AT_M = 45.0
RUN_AT_M = 69.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=0.005)
    options = parser.parse_args()

    raw = json.loads((data_root.case_dir() / "case_diverging_R1100.json").read_text(encoding="utf-8"))
    raw["run"].update({
        "x_start_m": RUN_AT_M,
        "seat_x_start_m": SEAT_AT_M,
        "duration_s": options.duration,
        "output_step_s": 5e-4,
        "max_solver_step_s": 5e-4,
        "method": "BDF",
        "jacobian": "analytic",
    })
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw.pop("initial_state", None)
    raw.pop("irregularity", None)

    path = Path(__file__).resolve().parents[2] / "scratch" / "s28" / "case_curve_contact.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    case = load_vehicle_case(path)

    speed = SPEED_KMH / 3.6
    dynamics = VehicleDynamics(case)
    topology = dynamics.topology
    print(f"coordinates {dynamics.dimension}   rails {len(case.rails)}   "
          f"track {type(dynamics.track).__name__}")
    print(f"run from {RUN_AT_M} m, seat at {SEAT_AT_M} m, {SPEED_KMH} km/h, "
          f"{options.duration} s")
    offsets = {str(wheel.id): float(wheel.lateral_offset_m) for wheel in case.wheels}
    print("wheel lateral offsets: " + ", ".join(f"{k} {v:+.4f}" for k, v in offsets.items()))

    q = np.zeros(dynamics.dimension)
    v = np.zeros(dynamics.dimension)
    print("\nrail cross sections at the first axle mileage (placement as loaded):")
    for index, rail in enumerate(case.rails):
        state = dynamics.track.local_state(q, v, index, RUN_AT_M + 10.0, speed)
        state_text = " ".join(f"{float(value):+.5f}" for value in state)
        sample = rail.bodies[0].series.sample(RUN_AT_M + 10.0) if rail.bodies else None
        span = ""
        if sample is not None:
            lateral = np.asarray(sample.profile.y_m, dtype=float)
            span = (f"  profile y {lateral.min():+.4f}..{lateral.max():+.4f}"
                    f" mean {lateral.mean():+.4f} n {lateral.size}")
        print(f"    {str(rail.id):<14s} local_state [{state_text}]{span}")

    result = simulate_vehicle(case)
    print(f"\nstatus {result.summary['result_status']}   "
          f"gates {sum(bool(value) for value in result.summary['gates'].values())}"
          f"/{len(result.summary['gates'])}")
    for name, value in result.summary["gates"].items():
        print(f"    {name:<34s} {value}")
    peak = result.summary["peak_normal_force_n"]
    if isinstance(peak, dict):
        peak_text = ", ".join(f"{key} {float(value):.1f}" for key, value in sorted(peak.items()))
    else:
        peak_text = f"{float(peak):.1f}"
    print(f"    peak normal [{peak_text}] N")
    print(f"    max penetration {float(result.summary['max_penetration_m']) * 1e6:.2f} um")

    for index in (0, len(result.contacts) - 1):
        frame = result.contacts[index]
        print("\ncontact table, frame {} of {} (t = {:.4f} s, {} entries):".format(
            index, len(result.contacts), float(result.times_s[index]), len(frame)))
        for key, value in sorted(frame.items()):
            geometry = value.geometry
            if geometry is None:
                print(f"    {key:<14s} no geometry   N {float(value.normal_force_n):10.1f}")
                continue
            print(f"    {key:<14s} N {float(value.normal_force_n):10.1f}  "
                  f"pen {float(geometry.penetration_m) * 1e6:8.2f} um  "
                  f"lever_y {float(geometry.lever_y_m):+8.5f}  "
                  f"lever_z {float(geometry.lever_z_m):+8.5f}  "
                  f"Fy {float(value.wheel_force_y_n):+9.1f}  "
                  f"slip_lat {float(value.slip_lateral_m_s):+.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
