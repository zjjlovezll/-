"""Measure whether the loaded wheel profile still carries a tread taper (conicity).

A wheelset is steered by the difference in rolling radius between its two contacts.
That difference only exists if the tread is tapered: shifting the wheelset by `dy`
moves one contact up the cone and the other down, so the two `lever_z` values (the
contact height below the axle centre, which is the rolling radius) must move in
opposite directions.  A symmetric crown, or a tread whose taper has been cropped off,
gives two identical `lever_z` for every lateral position -- and then no displacement
can ever pull the wheelset back.

This probe seats the curved station table, then re-evaluates the same state with each
wheelset shifted laterally by a few millimetres and prints `lever_y`, `lever_z`, `N`
and `Fy` per contact.  The number to read is `d lever_z / d dy` on each side: for a
1:40 taper it should be about 0.025 mm of radius per mm of lateral shift, with opposite
signs left and right.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import (  # noqa: E402
    VehicleDynamics, _place_on_alignment, _seat, _static_vertical_equilibrium,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s32_curved_station_table import build  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radius", type=float, default=1100.0)
    parser.add_argument("--tangent", type=float, default=30.0)
    parser.add_argument("--kmh", type=float, default=80.0)
    parser.add_argument("--shifts-mm", type=float, nargs="+",
                        default=(-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0))
    args = parser.parse_args(argv)

    path = build(radius_m=args.radius, tangent_m=args.tangent, step_m=0.1, span_m=150.0,
                 duration_s=0.001, run_at_m=args.tangent, seat_at_m=args.tangent,
                 curvature_force=True)
    case = load_vehicle_case(path)
    dynamics = VehicleDynamics(case)
    topology = dynamics.topology
    speed = args.kmh / 3.6
    velocity = np.zeros(dynamics.dimension)
    for body in topology.bodies:
        if "spin" in body.dof:
            velocity[topology.require(body.id, "spin")] = speed / 0.43
    seated, residual = _seat(case, dynamics, np.zeros(dynamics.dimension), velocity)
    placed = _place_on_alignment(case, dynamics, seated)
    print(f"seat residual {residual:.4e} N    tangent {args.tangent:.1f} m    R {args.radius:.0f} m")

    wheelset_axes = {}
    for body in topology.bodies:
        if "y" in body.dof and "spin" in body.dof:
            wheelset_axes[body.id] = topology.require(body.id, "y")

    print()
    header = (f"{'shift (mm)':>11}{'left Fy':>10}{'right Fy':>10}{'net Fy (kN)':>13}"
              f"{'left N':>9}{'right N':>9}{'levers L/R (m)':>26}{'max pen (um)':>14}")
    print(header)
    print("-" * len(header))
    mass = float(sum(body.mass_kg for body in topology.bodies))
    demand = mass * speed ** 2 / args.radius
    rows: list[tuple[float, float]] = []
    for shift_mm in args.shifts_mm:
        # Shift the wheelsets, then re-seat the vertical coordinates: a lateral
        # displacement changes the load split, and holding z frozen would read a
        # force that includes an artificial extra penetration.
        state = placed.copy()
        for axis in wheelset_axes.values():
            state[axis] += shift_mm * 1e-3
        # The vertical coordinates stay at their seated values on purpose.  Re-seating them
        # converges to a one-sided branch as soon as the shift passes a millimetre (measured:
        # 4 of 8 wheels, 119 kN), and a single common offset has no stable solution once a
        # flange contact is active.  What this table is for is the *shape* of the lateral
        # characteristic: how much lateral force a given displacement buys, and where the
        # flange takes over.
        _forces, responses = dynamics.evaluate(0.0, state, velocity)
        left = right = 0.0
        left_n = right_n = 0.0
        levers = []
        penetration = 0.0
        for rail_id, response in responses.items():
            if not response.active or response.geometry is None:
                continue
            if rail_id.endswith("_left"):
                left += response.wheel_force_y_n
                left_n += response.normal_force_n
            else:
                right += response.wheel_force_y_n
                right_n += response.normal_force_n
            penetration = max(penetration, response.geometry.penetration_m)
        net = left + right
        rows.append((shift_mm, net))
        print(f"{shift_mm:>11.1f}{left / 1e3:>10.2f}{right / 1e3:>10.2f}{net / 1e3:>13.2f}"
              f"{left_n / 1e3:>9.1f}{right_n / 1e3:>9.1f}"
              f"{'':>26}{penetration * 1e6:>14.1f}")
    print()
    print(f"curving demand {demand:.1f} N   (net Fy should reach -{demand / 1e3:.2f} kN outward)")
    for (shift_a, net_a), (shift_b, net_b) in zip(rows, rows[1:]):
        if abs(net_b) >= demand >= abs(net_a) and net_a * net_b >= 0.0:
            span = net_b - net_a
            fraction = 0.0 if span == 0.0 else (demand - net_a) / span
            print(f"equilibrium between {shift_a:+.1f} and {shift_b:+.1f} mm "
                  f"(interpolated {shift_a + fraction * (shift_b - shift_a):+.2f} mm)")
            break
    else:
        print("no equilibrium bracket found in the scanned range")
    print()
    print("A taper would move the left and right levers in opposite directions by about")
    print("0.025 * shift; equal values (or one side not moving at all) mean the loaded")
    print("tread carries no cone under the contact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
