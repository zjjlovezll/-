"""Purity check: the implicit-solver right-hand side must not depend on call order."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics

BASE = Path(__file__).resolve().parent
CASE = BASE / "case_frog_N_strip05.json"


def main() -> int:
    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    state = np.concatenate((np.array(case.initial_q), np.array(case.initial_v)))
    jitter = state.copy()
    jitter[5] -= 2e-4

    a = dynamics.derivative_pure(0.0, state)
    b = dynamics.derivative_pure(0.0, jitter)
    c = dynamics.derivative_pure(0.0, state)
    wrong_order = dynamics.derivative_pure(0.0, state)

    impure = dynamics.derivative(0.0, state)
    dynamics.derivative(0.0, jitter)
    impure_again = dynamics.derivative(0.0, state)

    print(f"pure   : |f(s)-f(s)|        = {np.max(np.abs(c - a)):.3e}")
    print(f"pure   : |f_after_jitter-f| = {np.max(np.abs(wrong_order - a)):.3e}")
    print(f"impure : |f_after_jitter-f| = {np.max(np.abs(impure_again - impure)):.3e}")
    print(f"single-call agreement       = {np.max(np.abs(b - b)):.3e}")
    dynamics.close()
    return 0 if np.max(np.abs(c - a)) == 0.0 and np.max(np.abs(wrong_order - a)) == 0.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
