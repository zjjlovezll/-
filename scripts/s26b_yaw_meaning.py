"""Does the yaw coordinate mean the same thing to the alignment and to the creep law?

``_align_to_track_frame`` writes ``yaw = arctan(dy/ds)`` -- a body's heading in the ground frame.
``contact.py:732`` turns the same coordinate into an angle of attack: ``creep_attack_velocity =
travel * yaw``.  At the middle of the corrugation patch the 18 turnout's design line has moved
+0.475 m and turned 0.0302 rad, so an aligned wheelset is handed ``travel * yaw = 0.67 m/s`` of
lateral creep that a wheelset following the curve does not have.

The comparison below holds everything else fixed: same mileage, same lateral shift, same spin, same
vertical seat.  Only the yaw differs.  If the alignment's convention is the one the creep law
expects, adding the tangent heading must leave the vertical seat working, because a wheelset that
follows the curve is not attacking it.  If the same coordinate is being read as an angle of attack,
the seat acquires a lateral force it has no coordinate to balance and stops converging.

Run:  python -X utf8 scripts/s26b_yaw_meaning.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import (
    SimulationFailure,
    VehicleDynamics,
    _gauge_centre,
    _seat,
)

SPEED_KMH = 80.0
PATCH_M = (79.6, 83.6)


def build(mileage_m: float):
    raw = json.loads((data_root.case_dir() / "case_diverging_R1100.json").read_text(encoding="utf-8"))
    raw["run"].update({
        "x_start_m": mileage_m,
        "duration_s": 0.01,
        "output_step_s": 0.01,
        # The lateral shift and the heading are applied by this script, not by the loader: that is
        # what lets the two variants differ in the yaw alone.
        "align_to_track": False,
    })
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw.pop("initial_state", None)
    path = Path(__file__).resolve().parents[2] / "scratch" / "seat26" / "yaw_meaning.json"
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
    weight = case.vehicle.gravity_m_s2 * total_mass
    share = weight / 8.0

    lateral, slope = _gauge_centre(case, start, dynamics, speed)
    print(f"mileage                  : {start:.2f} m")
    print(f"design-line offset       : {lateral:+.5f} m   tangent {slope:+.5f} rad")
    print(f"spurious lateral creep   : {speed * slope:+.4f} m/s at that yaw "
          f"({slope * 1e3:+.2f} mrad of attack)")
    print(f"centripetal force needed : {total_mass * speed * speed / 1100.0:+.1f} N")
    print(f"even share per wheel     : {share:.1f} N\n")

    velocity = np.zeros(dynamics.dimension)
    radius = float(case.vehicle.nominal_wheel_radius_m)
    for body in topology.wheelsets():
        velocity[topology.require(body.id, "spin")] = speed / radius

    for convention in ("yaw = 0", "yaw = tangent"):
        q = np.zeros(dynamics.dimension)
        for body in topology.bodies:
            if "y" in body.dof:
                q[topology.require(body.id, "y")] = lateral
            if convention == "yaw = tangent" and "yaw" in body.dof:
                q[topology.require(body.id, "yaw")] = slope
        try:
            seated, residual = _seat(case, dynamics, q, velocity)
        except SimulationFailure as error:
            print(f"{convention:<14s}: seat FAILED -- {error}")
            continue
        dynamics.placement_enabled = True
        force, contacts = dynamics.evaluate(0.0, seated, velocity)
        loaded = {key: value for key, value in contacts.items()
                  if abs(float(value.normal_force_n)) > 1.0}
        lateral_force = sum(float(value.wheel_force_y_n) for value in loaded.values())
        vertical_force = sum(float(value.wheel_force_z_n) for value in loaded.values())
        slip = [float(value.slip_lateral_m_s) for value in loaded.values()]
        print(f"{convention:<14s}: residual {residual:.3e} N  patches {len(loaded)}  "
              f"sum Fy {lateral_force:+11.1f} N  sum Fz {vertical_force:+11.1f} N")
        print(f"{'':<14s}  y/Q {abs(lateral_force) / max(abs(vertical_force), 1.0):+.4f}   "
              f"slip_lateral {min(slip):+.4f}..{max(slip):+.4f} m/s" if slip else "")
        for key, value in sorted(loaded.items()):
            print(f"    {key:<12s} N {float(value.normal_force_n):9.1f}  "
                  f"ratio {float(value.normal_force_n) / share:5.3f}x  "
                  f"Fy {float(value.wheel_force_y_n):+9.1f}  "
                  f"slip_lat {float(value.slip_lateral_m_s):+.5f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
