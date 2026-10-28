"""Measure the yaw balance of one wheelset on the curved station table.

The curved route never settles, and every other candidate has been ruled out by
measurement (damping, the crown gauge, the absolute heading, the frame velocity).
What is left is the yaw moment: a wheelset on a curve is steered by the couple the
two longitudinal creep forces make, and if that couple cannot be generated the
contact can only meet the 21.8 kN demand by pressing deeper.

This script prints, at the seated state with the wheels rolling, what the creep law
actually produces:

* per contact: normal force, `slip_x`, longitudinal force, `slip_lateral`, lateral
  force, `lever_y`, `lever_z`;
* per wheelset: yaw angle, the creep yaw moment ``-sum(lever_y * F_x)``, the lateral
  force sum, and the ratio of the former to the primary yaw stiffness moment.

No new physics is added: every number is read straight out of one `evaluate` call.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics, _place_on_alignment, _seat  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s32_curved_station_table import build  # noqa: E402

SHARE_N = 59_662.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radius", type=float, default=1100.0)
    parser.add_argument("--tangent", type=float, default=30.0)
    parser.add_argument("--kmh", type=float, default=80.0)
    parser.add_argument("--step", type=float, default=0.1)
    parser.add_argument("--span", type=float, default=150.0)
    args = parser.parse_args(argv)

    path = build(radius_m=args.radius, tangent_m=args.tangent, step_m=args.step,
                 span_m=args.span, duration_s=0.001, run_at_m=args.tangent,
                 seat_at_m=args.tangent, curvature_force=True)
    case = load_vehicle_case(path)
    dynamics = VehicleDynamics(case)
    speed = args.kmh / 3.6
    velocity = np.zeros(dynamics.dimension)
    topology = dynamics.topology
    for body in topology.bodies:
        if "spin" not in body.dof:
            continue
        velocity[topology.require(body.id, "spin")] = speed / 0.43

    seated, residual = _seat(case, dynamics, np.zeros(dynamics.dimension), velocity)
    placed = _place_on_alignment(case, dynamics, seated)
    _forces, responses = dynamics.evaluate(0.0, placed, velocity)

    print(f"seat residual {residual:.4e} N    speed {args.kmh:.1f} km/h "
          f"({speed:.4f} m/s)    curvature 1/{args.radius:.0f} m")
    mass = float(sum(body.mass_kg for body in topology.bodies))
    print(f"spin {speed / 0.43:.4f} rad/s    total mass {mass:.0f} kg    "
          f"demand m v^2/R {mass * speed ** 2 / args.radius:.1f} N")
    print()
    header = (f"{'rail':<14}{'N (kN)':>9}{'x/N':>8}{'slip_x':>10}{'Fx (kN)':>9}"
              f"{'slip_lat':>10}{'Fy (kN)':>9}{'lever_y':>9}{'lever_z':>9}")
    print(header)
    print("-" * len(header))
    moments: dict[str, float] = {}
    for rail_id, response in sorted(responses.items()):
        if not response.active or response.geometry is None:
            continue
        geometry = response.geometry
        normal = response.normal_force_n
        print(f"{rail_id:<14}{normal / 1e3:>9.2f}{normal / SHARE_N:>8.3f}"
              f"{response.slip_x_m_s:>10.6f}{response.longitudinal_force_n / 1e3:>9.2f}"
              f"{response.slip_lateral_m_s:>10.6f}{response.wheel_force_y_n / 1e3:>9.2f}"
              f"{geometry.lever_y_m:>9.5f}{geometry.lever_z_m:>9.5f}")
        # `axle1_left` belongs to body `wheelset1`; the identifiers do not match without this map.
        axle = "wheelset" + rail_id.split("_")[0].removeprefix("axle")
        moments[axle] = moments.get(axle, 0.0) - geometry.lever_y_m * response.longitudinal_force_n

    print()
    k_yaw = float(case.vehicle.primary.k_yaw_nm_rad)
    print(f"primary yaw stiffness {k_yaw / 1e6:.3f} MN.m/rad")
    print(f"{'axle':<10}{'Fx couple (kN.m)':>18}{'yaw (mrad)':>12}{'k*yaw (kN.m)':>14}"
          f"{'Fy sum (kN)':>13}")
    topology = dynamics.topology
    for body in topology.bodies:
        if "yaw" not in body.dof or "y" not in body.dof:
            continue
        axle = body.id
        yaw = float(placed[topology.require(axle, "yaw")])
        lateral = 0.0
        for rail_id, response in responses.items():
            if response.active and response.geometry is not None and rail_id.startswith(axle + "_"):
                lateral += response.wheel_force_y_n
        couple = moments.get(axle, 0.0)
        print(f"{axle:<10}{couple / 1e3:>18.2f}{yaw * 1e3:>12.3f}"
              f"{k_yaw * yaw / 1e3:>14.2f}{lateral / 1e3:>13.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
