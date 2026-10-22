"""Decision experiment: is the normal force N(delta) discontinuous at contact onset?

If N jumps by O(100 kN) for a micrometre change of wheel height, the right-hand side is
discontinuous and no ODE solver can be stable across it (regularise the law). If N is
continuous and only its slope jumps, the implicit failure is a tolerance/step issue.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics

BASE = Path(__file__).resolve().parent
case = load_vehicle_case(BASE / "case_full12_cap05.json")
dynamics = VehicleDynamics(case)
q = np.array(case.initial_q, dtype=float)
v = np.zeros(dynamics.dimension)

print(f"{'sink_um':>8}{'N_right_kN':>12}{'N_left_kN':>11}{'pen_um':>9}")
previous = None
for sink_um in (-300.0, -200.0, -150.0, -100.0, -50.0, -20.0, -10.0, -5.0, -2.0, -1.0, 0.0):
    trial = q.copy()
    trial[5 * 0 + 1] -= sink_um * 1e-6
    force, contacts = dynamics.evaluate(0.0, trial, v)
    right = contacts["axle1_right"]
    left = contacts["axle1_left"]
    print(f"{sink_um:>8.1f}{right.normal_force_n / 1e3:>12.3f}"
          f"{left.normal_force_n / 1e3:>11.3f}"
          f"{1e6 * (right.geometry.penetration_m if right.geometry else 0.0):>9.3f}")
    if previous is not None and sink_um - previous[0] <= 2.0:
        jump = abs(right.normal_force_n - previous[1])
        if jump > 20e3:
            print(f"  -> jump {jump / 1e3:.1f} kN over {sink_um - previous[0]:.1f} um")
    previous = (sink_um, right.normal_force_n)
dynamics.close()
