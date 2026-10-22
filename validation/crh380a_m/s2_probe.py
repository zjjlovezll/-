"""Probe: which entry of which column is wrong, and what the geometry looks like."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from velch.jacobian import JacobianAssembler  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import (  # noqa: E402
    VehicleDynamics, _static_vertical_equilibrium)

SOURCE = HERE / "case_full12_cap05.json"

case = load_vehicle_case(SOURCE)
dynamics = VehicleDynamics(case)
q = np.array(case.initial_q, dtype=float)
v = np.array(case.initial_v, dtype=float)
q, residual = _static_vertical_equilibrium(case, dynamics, q, v)
n = dynamics.dimension
print("n", n, "residual", residual)

t_s = 0.0
assembler = JacobianAssembler(dynamics)
ana_q, ana_v = assembler.blocks(t_s, q, v)

scale = np.maximum(1.0, np.abs(np.concatenate((q, v))))
step = 1.0e-7
neq = np.empty((n, n))
for index in range(n):
    delta = step * scale[index]
    state = np.concatenate((q, v))
    plus = state.copy(); plus[index] += delta
    minus = state.copy(); minus[index] -= delta
    neq[:, index] = ((dynamics.derivative_pure(t_s, plus)[n:]
                      - dynamics.derivative_pure(t_s, minus)[n:]) / (2.0 * delta))

col_scale = np.max(np.abs(neq), axis=0)
labels = []
for i in range(4):
    labels += [f"a{i+1}_y", f"a{i+1}_z", f"a{i+1}_r", f"a{i+1}_s", f"a{i+1}_ya"]
for i in range(2):
    labels += [f"b{i+1}_y", f"b{i+1}_z", f"b{i+1}_r", f"b{i+1}_p", f"b{i+1}_ya"]
labels += ["cb_y", "cb_z", "cb_r", "cb_p", "cb_ya"]
nrail = n - 35
labels += [f"rail{i}_{'yz'[k % 2]}" for i in range(nrail // 2) for k in range(2)]

print(f"\n{'col':>3}{'label':>10}{'|Jfd|max':>12}{'relerr':>10}  worst rows")
for j in range(n):
    if col_scale[j] <= 0:
        continue
    err = np.abs(ana_q[:, j] - neq[:, j]) / col_scale[j]
    if err.max() > 1e-6:
        top = np.argsort(-np.abs(ana_q[:, j] - neq[:, j]))[:3]
        detail = " ".join(f"[{i}]a={ana_q[i,j]:+.4e} fd={neq[i,j]:+.4e}" for i in top)
        print(f"{j:>3}{labels[j]:>10}{col_scale[j]:>12.3e}{err.max():>10.2e}  {detail}")

print("\n-- geometry of each contact at t=0 --")
for rail_index, rail in enumerate(case.rails):
    for resp in dynamics.body_contacts.get(rail.id, ()):
        g = resp.geometry
        if g is None:
            continue
        print(f"{rail.id:>6} auc={rail.axle_index} act={resp.active} N={resp.normal_force_n:+.1f} "
              f"y={g.y_m:+.6f} pen={g.penetration_m*1e6:+.4f}um "
              f"ny={g.normal_y:+.6f} nz={g.normal_z:+.6f} "
              f"levy={g.lever_y_m:+.6f} levz={g.lever_z_m:+.9f} C={g.stiffness_n_m_1p5:.4e} "
              f"R*={g.radius_star_m:.5f}")
        row = assembler._kinematic_row(rail_index, 0.0, g)
        nz = np.flatnonzero(row)
        print("      row:", {labels[k]: f"{row[k]:+.6f}" for k in nz})
print()
