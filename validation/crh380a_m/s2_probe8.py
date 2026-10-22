"""Is the 1e-3 residual on the curved-profile rails a real derivative error or
finite-difference pollution?  Sweep the step."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from velch.vehicle import load_vehicle_case                   # noqa: E402
from velch.vehicle_solver import (                            # noqa: E402
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


def normal_force(dyn, t_s, q, v, index):
    dyn.contact_partials = True
    dyn.evaluate(t_s, q, v)
    for response in dyn.body_contacts.get(dyn.case.rails[index].id, ()):
        if response.active and response.geometry is not None:
            return response.normal_force_n, response.geometry
    return 0.0, None


def main() -> None:
    case = load_vehicle_case(SOURCE)
    dyn, q, v = _equilibrated(case)
    t_s = 0.70
    for index in (5, 4, 6, 7, 0):
        _f0, geom0 = normal_force(dyn, t_s, q, v, index)
        rail = case.rails[index]
        wh = 5 * rail.axle_index
        parts = geom0.partials
        print(f"\n rail{index} N={_f0:.6f} pen={geom0.penetration_m * 1e6:.4f}um "
              f"ana(dN/dz)={parts.normal_force_n[1]:+.9e}")
        for col, k in ((wh + 1, 1), (wh, 0), (wh + 2, 2)):
            row = []
            for h in (1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3):
                qp = q.copy(); qm = q.copy()
                qp[col] += h; qm[col] -= h
                fp, _ = normal_force(dyn, t_s, qp, v, index)
                fm, _ = normal_force(dyn, t_s, qm, v, index)
                fd = (fp - fm) / (2.0 * h)
                rel = abs(parts.normal_force_n[k] - fd) / max(abs(fd), 1e-30)
                row.append(f"h={h:.0e} fd={fd:+.8e} rel={rel:.2e}")
            print(f"  col{col} " + "\n        ".join(row))


if __name__ == "__main__":
    main()
