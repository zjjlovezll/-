"""Trace the straight-route vertical seat: which rows refuse to close?

``_static_vertical_equilibrium`` stops with "no seed converged; `gtol`", which says the least squares
stalled but not where.  This repeats the same problem by hand -- the same unknown rows, the same
residual scaling (force / 1e5), the same solver settings -- and then prints, at the stopping point:

* every residual row by name, so a row that cannot close is named;
* the contact table, so a wheel that never touches is visible;
* how many evaluations were rejected by the slope guard.

No physics is added and nothing is relaxed; it is the existing problem, read out.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from velch import vehicle_solver
from velch.vehicle import load_vehicle_case

EVEN_SHARE_N = 59_662.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    options = parser.parse_args()

    case = load_vehicle_case(options.case)
    dynamics = vehicle_solver.VehicleDynamics(case)
    topology = dynamics.topology
    q = np.zeros(dynamics.dimension)
    v = np.zeros(dynamics.dimension)
    speed = float(case.vehicle.travel_speed_m_s)
    for index in range(len(case.wheels) // 2):
        v[topology.require(f"wheelset{index + 1}", "spin")] = speed / float(
            case.vehicle.nominal_wheel_radius_m
        )

    labels: list[str] = []
    indices: list[int] = []
    for body in topology.bodies:
        try:
            indices.append(topology.require(body.id, "z"))
        except Exception:
            continue
        labels.append(f"{body.id}.z")
    if case.track_kind == "local_compliant":
        for index in range(len(case.rails)):
            indices.append(topology.body_dimension + 2 * index + 1)
            labels.append(f"rail{index}.z")
    print(f"coordinates {dynamics.dimension}  unknowns {len(indices)}  "
          f"track {case.track_kind}  x_start {case.run.x_start_m:.1f} m")

    base = q.copy()
    barriered: list[int] = []

    def residual(delta: np.ndarray) -> np.ndarray:
        state = base.copy()
        state[indices] = delta
        try:
            result = dynamics.evaluate(0.0, state, v)
        except Exception:
            barriered.append(1)
            return np.full(len(indices), vehicle_solver._SEAT_BARRIER_RESIDUAL)
        force = np.asarray(result, dtype=float)
        return force[indices] / 1e5

    start = base[indices].copy()
    solution = least_squares(
        residual, start, method="trf", xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=800
    )
    print(f"termination {solution.status} {solution.message}  |r| {np.abs(solution.fun).max():.3e}  "
          f"barrier hits {len(barriered)}")
    order = np.argsort(-np.abs(solution.fun))
    for position in order[:6]:
        print(f"    {labels[position]:<16} {solution.fun[position] * 1e5:+.1f} N")
    state = base.copy()
    state[indices] = solution.x
    dynamics.evaluate(0.0, state, v)
    for rail_id, response in sorted(dynamics.body_contacts.items()):
        response = response[0] if isinstance(response, tuple) else response
        geometry = response.geometry
        pen = 0.0 if geometry is None else float(geometry.penetration_m) * 1e6
        print(f"    {rail_id:<14} N {response.normal_force_n / EVEN_SHARE_N:6.3f}x  pen {pen:8.2f} um"
              f"  lever_y {0.0 if geometry is None else float(geometry.lever_y_m):+.5f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
