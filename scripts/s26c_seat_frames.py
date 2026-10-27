"""Why can the vertical seat not be solved inside the curve, even with the vehicle aligned?

``_seat`` deliberately clears the curve placement while it solves, so the contact search sees the
station table's own geometry (which is already curved on this turnout) but not the analytic
``y = s^2/(2R)`` placement.  The alignment, on the other hand, shifts the vehicle by the design-line
offset.  If those two disagree, the wheels stand next to their rails and no vertical seat can put
eight patches under load -- and the failure message looks like a solver problem.

This prints the same eight-patch table for the four combinations of (placement on/off) x (vehicle
shifted/not shifted) at the middle of the corrugation patch, with the wheels pulled down by the
static penetration so that a well-posed case does carry load.

Run:  python -X utf8 scripts/s26c_seat_frames.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _gauge_centre

SPEED_KMH = 80.0
PATCH_M = (79.6, 83.6)
STATIC_PENETRATION_M = 65.47e-6


def build(mileage_m: float):
    raw = json.loads((data_root.case_dir() / "case_diverging_R1100.json").read_text(encoding="utf-8"))
    raw["run"].update({"x_start_m": mileage_m, "duration_s": 0.01, "output_step_s": 0.01,
                       "align_to_track": False})
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw.pop("initial_state", None)
    path = Path(__file__).resolve().parents[2] / "scratch" / "seat26" / "seat_frames.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return load_vehicle_case(path)


def main() -> int:
    start = float(np.mean(PATCH_M))
    case = build(start)
    dynamics = VehicleDynamics(case)
    topology = dynamics.topology
    speed = abs(float(case.vehicle.travel_speed_m_s))
    total_mass = sum(body.mass_kg for body in topology.bodies)
    share = case.vehicle.gravity_m_s2 * total_mass / 8.0

    lateral, slope = _gauge_centre(case, start, dynamics, speed)
    print(f"mileage {start:.2f} m   design-line offset {lateral:+.5f} m   "
          f"tangent {slope:+.5f} rad   even share {share:.1f} N\n")

    velocity = np.zeros(dynamics.dimension)
    radius = float(case.vehicle.nominal_wheel_radius_m)
    for body in topology.wheelsets():
        velocity[topology.require(body.id, "spin")] = speed / radius

    for placement in (False, True):
        for shifted in (False, True):
            dynamics.placement_enabled = placement
            q = np.zeros(dynamics.dimension)
            for body in topology.bodies:
                if "z" in body.dof:
                    q[topology.require(body.id, "z")] = -STATIC_PENETRATION_M
                if shifted and "y" in body.dof:
                    q[topology.require(body.id, "y")] = lateral
            force, contacts = dynamics.evaluate(0.0, q, velocity)
            loaded = {key: value for key, value in contacts.items()
                      if abs(float(value.normal_force_n)) > 1.0}
            total = sum(float(value.normal_force_n) for value in loaded.values())
            print(f"placement {str(placement):<5s}  vehicle shifted {str(shifted):<5s}  "
                  f"patches {len(loaded)}  sum N {total:11.1f} N  "
                  f"weight {case.vehicle.gravity_m_s2 * total_mass:11.1f} N")
            for key, value in sorted(loaded.items()):
                print(f"    {key:<12s} N {float(value.normal_force_n):10.1f}  "
                      f"ratio {float(value.normal_force_n) / share:5.3f}x  "
                      f"pen {float(value.penetration_m) * 1e6:8.2f} um  "
                      f"lever_y {float(value.lever_y_m):+8.5f}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
