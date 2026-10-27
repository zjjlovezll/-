"""Why does the vertical seat fail on the rebuilt (B041) diverging case?

Prints the residual the least-squares solver reaches, row by row, plus the contact table at that point.
Same unknown set as `_static_vertical_equilibrium`: every body with a z row and the vertical row of
every elastic rail.

Run:  python -X utf8 scripts/s30d_seat_diagnose.py [--case PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics

EVEN_SHARE_N = 59_662.0
SPEED_KMH = 80.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--seat-at", type=float, default=45.0)
    parser.add_argument("--run-at", type=float, default=69.0)
    options = parser.parse_args()

    raw = json.loads(Path(options.case).read_text(encoding="utf-8"))
    raw["run"].update({"x_start_m": options.run_at, "seat_x_start_m": options.seat_at,
                       "duration_s": 0.01, "output_step_s": 0.01, "method": "BDF",
                       "jacobian": "analytic"})
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw.pop("initial_state", None)
    prepared = Path(options.case).with_name("case_diagnose.json")
    prepared.write_text(json.dumps(raw, indent=1), encoding="utf-8")

    case = load_vehicle_case(prepared)
    dynamics = VehicleDynamics(case)
    speed = SPEED_KMH / 3.6
    velocity = np.zeros(dynamics.dimension)
    radius = float(case.vehicle.nominal_wheel_radius_m)
    for body in dynamics.topology.wheelsets():
        velocity[dynamics.topology.require(body.id, "spin")] = speed / radius

    names: list[str] = []
    indices: list[int] = []
    for body in dynamics.topology.bodies:
        if "z" in body.dof:
            names.append(f"{body.id}.z")
            indices.append(dynamics.topology.require(body.id, "z"))
    for rail_index in range(len(case.rails)):
        names.append(f"rail{rail_index}.z")
        indices.append(dynamics.topology.body_dimension + 2 * rail_index + 1)
    indices_array = np.asarray(indices, dtype=int)
    print(f"{len(indices)} unknowns: {', '.join(names)}")

    calls = {"n": 0}

    def residual(delta: np.ndarray) -> np.ndarray:
        state = np.zeros(dynamics.dimension)
        state[indices_array] = delta
        if calls["n"] == 0:
            dynamics.placement_enabled = False
        calls["n"] += 1
        _, _ = dynamics.evaluate(0.0, state, velocity)
        return np.asarray(dynamics.force[indices_array], dtype=float) / 1.0e5

    for drop_um in (0.0, 32.7, 65.5, 98.2, 131.0, -65.5):
        x0 = np.zeros(len(indices))
        for k, name in enumerate(names):
            if name.endswith(".z") and "wheelset" in name:
                x0[k] = -drop_um * 1e-6
        solution = least_squares(residual, x0, method="trf",
                                 xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=800)
        worst = np.argsort(-np.abs(solution.fun))[:6]
        print(f"\nseed drop {drop_um:+7.1f} um -> |r|max {np.abs(solution.fun).max():.4e} "
              f"({solution.status}: {solution.message.strip()})  nfev {solution.nfev}")
        for k in worst:
            print(f"    {names[k]:<18s} {solution.fun[k]:+12.4e}")
        state = np.zeros(dynamics.dimension)
        state[indices_array] = solution.x
        _, contacts = dynamics.evaluate(0.0, state, velocity)
        loaded = 0
        for key, value in sorted(contacts.items()):
            geometry = value.geometry
            if geometry is None:
                continue
            loaded += 1
            print(f"      {key:<14s} N {float(value.normal_force_n):9.1f} "
                  f"({float(value.normal_force_n) / EVEN_SHARE_N:5.3f}x) "
                  f"pen {float(geometry.penetration_m) * 1e6:8.2f} um "
                  f"lever_y {float(geometry.lever_y_m):+8.5f}")
        print(f"      loaded {loaded}/8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
