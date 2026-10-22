"""Diagnose the residual dq error at t=0.70: which contacts are live, and which
entries still disagree with the central difference."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from velch.contact import _absolute_arrays, _grid_slope          # noqa: E402
from velch.jacobian import JacobianAssembler                     # noqa: E402
from velch.vehicle import load_vehicle_case                      # noqa: E402
from velch.vehicle_solver import (                               # noqa: E402
    VehicleDynamics,
    _static_vertical_equilibrium,
)

SOURCE = HERE / "case_full12_cap05.json"


def _equilibrated(case):
    dynamics = VehicleDynamics(case)
    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    if case.equilibrate_vertical:
        q, _residual = _static_vertical_equilibrium(case, dynamics, q, v)
    return dynamics, q, v


def main() -> None:
    case = load_vehicle_case(SOURCE)
    dyn, q, v = _equilibrated(case)

    asm = JacobianAssembler(dyn)

    for t_s in (0.70, 0.45):
        print(f"\n=== t={t_s:.2f} live contacts ===")
        dyn.contact_partials = True
        dyn.evaluate(t_s, q, v)
        n_contacts = 0
        for index, rail in enumerate(case.rails):
            x = (case.run.x_start_m + case.vehicle.travel_speed_m_s * t_s
                 + case.vehicle.axle_offsets_m[rail.axle_index])
            for response in dyn.body_contacts.get(rail.id, ()):
                if not response.active or response.geometry is None:
                    continue
                g = response.geometry
                n_contacts += 1
                print(f" rail{index} x={x:8.4f} N={response.normal_force_n:9.3f} "
                      f"y_c={g.y_m:+.6f} pen={g.penetration_m * 1e6:7.3f}um "
                      f"ny={g.normal_y:+.6f} lever_z={g.lever_z_m:+.6f} "
                      f"partials={'yes' if g.partials is not None else 'NO'}")
                if g.partials is not None:
                    print("   dN/dq   " + " ".join(f"{v_:+.4e}" for v_ in g.partials.normal_force_n))
                    print("   dslope  " + " ".join(f"{v_:+.4e}" for v_ in g.partials.normal_slope))
                    print("   dleverY " + " ".join(f"{v_:+.4e}" for v_ in g.partials.lever_y_m))
                    print("   dleverZ " + " ".join(f"{v_:+.4e}" for v_ in g.partials.lever_z_m))
        print(f" live contacts: {n_contacts}")

        aq, _av = asm.blocks(t_s, q, v)
        h = 1e-7
        cols, rows = [], []
        for j in range(dyn.dimension):
            qp = q.copy(); qm = q.copy()
            step = h * max(1.0, abs(q[j]))
            qp[j] += step; qm[j] -= step
            fp = dyn.derivative_pure(t_s, np.concatenate([qp, v]))[dyn.dimension:]
            fm = dyn.derivative_pure(t_s, np.concatenate([qm, v]))[dyn.dimension:]
            fd = (fp - fm) / (2.0 * step)
            err = np.abs(aq[:, j] - fd).max() / max(np.abs(fd).max(), 1e-30)
            if err > 1e-5:
                col = int(np.argmax(np.abs(aq[:, j] - fd)))
                cols.append((err, j, col, aq[col, j], fd[col], np.abs(fd).max()))
        cols.sort(reverse=True)
        print(f" columns above 1e-5: {len(cols)}")
        for err, j, col, a, fdv, scale in cols[:10]:
            print(f"   col {j:2d} row {col:2d} err={err:.3e} a={a:+.9e} fd={fdv:+.9e} "
                  f"colscale={scale:.3e} diff={a - fdv:+.4e}")


if __name__ == "__main__":
    main()
