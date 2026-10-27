"""What is the lateral creep at the *seated* start of the curved turnout run?

An unseated probe carries no contact ("zero compared with zero"), so the number that matters has to
be read after the seat.  This seats the case exactly the way the solver does and then evaluates the
first frame, printing ``slip_lateral`` once with the route's lateral rate as shipped and once with
it forced to zero.

Run:  python -X utf8 scripts/s29b_seat_slip.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from velch import data_root
from velch.paths import PathTrack
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat

SPEED_KMH = 80.0
SEAT_AT_M = 45.0
RUN_AT_M = 69.0
EVEN_SHARE_N = 59_662.0


def build() -> object:
    raw = json.loads((data_root.case_dir() / "case_diverging_R1100.json").read_text(encoding="utf-8"))
    raw["run"].update({"x_start_m": RUN_AT_M, "seat_x_start_m": SEAT_AT_M,
                       "duration_s": 0.01, "output_step_s": 0.01,
                       "method": "BDF", "jacobian": "analytic"})
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw.pop("initial_state", None)
    raw.pop("irregularity", None)
    target = Path(__file__).resolve().parents[2] / "scratch" / "s29" / "case_seat_slip.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return load_vehicle_case(target)


def report(label: str) -> None:
    case = build()
    dynamics = VehicleDynamics(case)
    speed = SPEED_KMH / 3.6
    velocity = np.zeros(dynamics.dimension)
    radius = float(case.vehicle.nominal_wheel_radius_m)
    for body in dynamics.topology.wheelsets():
        velocity[dynamics.topology.require(body.id, "spin")] = speed / radius
    seated, residual = _seat(case, dynamics, np.zeros(dynamics.dimension), velocity)
    _, contacts = dynamics.evaluate(0.0, seated, velocity)
    print(f"\n=== lateral rate {label} ===")
    print(f"seat residual {residual:.3e} N")
    total_lateral = 0.0
    for key, value in sorted(contacts.items()):
        geometry = value.geometry
        if geometry is None:
            print(f"    {key:<14s} no geometry")
            continue
        total_lateral += float(value.wheel_force_y_n)
        print(f"    {key:<14s} N {float(value.normal_force_n):9.1f} "
              f"({float(value.normal_force_n) / EVEN_SHARE_N:5.3f}x)  "
              f"pen {float(geometry.penetration_m) * 1e6:7.2f} um  "
              f"lever_y {float(geometry.lever_y_m):+8.5f}  "
              f"Fy {float(value.wheel_force_y_n):+9.1f}  "
              f"slip_lat {float(value.slip_lateral_m_s):+.4f}")
    mass = sum(body.mass_kg for body in dynamics.topology.bodies)
    print(f"    sum Fy {total_lateral:+9.1f} N   centripetal needed "
          f"{mass * speed * speed / 1100.0:+.1f} N")


def main() -> int:
    original = PathTrack.lateral_velocity_m_s
    try:
        report("as shipped")
        PathTrack.lateral_velocity_m_s = lambda self, station_m, speed_m_s: 0.0
        report("forced to zero")
    finally:
        PathTrack.lateral_velocity_m_s = original
    return 0


if __name__ == "__main__":
    sys.exit(main())
