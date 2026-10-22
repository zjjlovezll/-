"""Bounded numerical-method probe for the synthetic contact-switch case."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from velch.model import load_case
from velch.solver import Dynamics

case = load_case(Path(__file__).resolve().parents[1] / "examples/synthetic_transfer/case.json")
dynamics = Dynamics(case)
initial = np.array((*case.initial_q, *case.initial_v))
records = []
for method in ("DOP853", "Radau"):
    start = time.perf_counter()
    solution = solve_ivp(dynamics.derivative, (0.0, case.run.duration_s), initial,
                         method=method, rtol=case.run.rtol, atol=case.run.atol,
                         max_step=case.run.max_solver_step_s)
    records.append({"method": method, "success": solution.success,
                    "nfev": solution.nfev, "wall_s": round(time.perf_counter() - start, 3),
                    "final_wheel_z_m": float(solution.y[1, -1])})
print(json.dumps(records, indent=2))
