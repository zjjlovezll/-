"""Probe 3: decompose d(force)/dq per contact, and inspect strip integral internals."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import (  # noqa: E402
    VehicleDynamics, _static_vertical_equilibrium)

SOURCE = HERE / "case_full12_cap05.json"
case = load_vehicle_case(SOURCE)
dynamics = VehicleDynamics(case)
q0 = np.array(case.initial_q, dtype=float)
v0 = np.array(case.initial_v, dtype=float)
q0, residual = _static_vertical_equilibrium(case, dynamics, q0, v0)
n = dynamics.dimension
mass = np.asarray(dynamics.mass, dtype=float)
print("mass[0:6]", mass[:6])
print("dimension", n, "nq", dynamics.dimension_q if hasattr(dynamics, "dimension_q") else "?")

state0 = np.concatenate((q0, v0))


def responses(state):
    t = 0.0
    dynamics.evaluate(t, state[:n], state[n:])
    out = {}
    for rail in case.rails:
        for resp in dynamics.body_contacts.get(rail.id, ()):
            out[rail.id] = resp
    return out


base = responses(state0)
print("\nbase response left axle1:")
r = base["axle1_left"]
for f in ("normal_force_n", "normal_elastic_n", "normal_damping_n",
          "longitudinal_force_n", "lateral_tangent_force_n",
          "wheel_force_y_n", "wheel_force_z_n", "wheel_roll_moment_nm",
          "slip_x_m_s", "slip_lateral_m_s", "normal_approach_speed_m_s",
          "hertz_penetration_m", "normal_force_slope_n_m" if hasattr(r, "normal_force_slope_n_m") else "active"):
    print("   ", f, getattr(r, f, "n/a"))

coords = [(1, "a1_z"), (0, "a1_y"), (2, "a1_roll"), (36, "rail0_z"), (35, "rail0_y")]
fields = ("normal_force_n", "longitudinal_force_n", "lateral_tangent_force_n",
          "wheel_force_y_n", "wheel_force_z_n", "wheel_roll_moment_nm", "wheel_spin_moment_nm")
for idx, name in coords:
    h = 1.0e-7 * max(1.0, abs(q0[idx])) if idx not in (2,) else 1.0e-7
    sp = state0.copy(); sp[idx] += h
    sm = state0.copy(); sm[idx] -= h
    fp = dynamics.derivative_pure(0.0, sp)[n:]
    fm = dynamics.derivative_pure(0.0, sm)[n:]
    dforce = (fp - fm) / (2 * h)
    print(f"\n-- col {name} (idx {idx}) h={h:.1e}: d(force/dt) nonzero rows --")
    for row in np.flatnonzero(np.abs(dforce) > 1e-3 * np.abs(dforce).max()):
        print(f"    row {row:>2} dacc={dforce[row]:+.6e}  dforce={dforce[row] * mass[row]:+.6e}")
    bp = responses(sp)["axle1_left"]
    bm = responses(sm)["axle1_left"]
    print("    response FD:", {f: f"{(getattr(bp, f) - getattr(bm, f)) / (2 * h):+.6e}" for f in fields})
    gp, gm = bp.geometry, bm.geometry
    for f in ("y_m", "penetration_m", "normal_y", "normal_z", "tangent_y", "tangent_z",
              "lever_y_m", "lever_z_m", "stiffness_n_m_1p5", "radius_star_m", "half_width_m"):
        print(f"      d{f:<20} = {(getattr(gp, f) - getattr(gm, f)) / (2 * h):+.6e}")
print()
