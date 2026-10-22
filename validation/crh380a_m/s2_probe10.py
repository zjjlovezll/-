"""Which q-dependence of the contact *law* still escapes the Jacobian?

At t=0.70 the right-hand rails have a non-zero longitudinal profile slope
``rail_dz_ds``, which puts the damping channel into play; the damping reads the
equivalent penetration and the approach speed, both of which move with q.
Compare FD of ``penetration``, ``stiffness``, ``approach``, ``rail_dz_ds`` and
``normal`` against the two candidate decompositions.
"""
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
MODES = ("y_w", "z_w", "roll", "rail_y", "rail_z")


def _equilibrated(case):
    dynamics = VehicleDynamics(case)
    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    if case.equilibrate_vertical:
        q, _residual = _static_vertical_equilibrium(case, dynamics, q, v)
    return dynamics, q, v


def probe(dyn, t_s, q, v, index):
    dyn.contact_partials = True
    dyn.evaluate(t_s, q, v)
    for response in dyn.body_contacts.get(dyn.case.rails[index].id, ()):
        if response.active and response.geometry is not None:
            return response
    return None


def main() -> None:
    case = load_vehicle_case(SOURCE)
    dyn, q, v = _equilibrated(case)
    t_s = 0.70
    for index in (5, 4, 6, 7):
        base = probe(dyn, t_s, q, v, index)
        geom = base.geometry
        parts = geom.partials
        rail = case.rails[index]
        wh = 5 * rail.axle_index
        modes = (wh, wh + 1, wh + 2, 35 + 2 * index, 35 + 2 * index + 1)
        F = base.normal_elastic_n
        C = geom.stiffness_n_m_1p5
        delta = geom.penetration_m
        print(f"\n rail{index} F={F:.6f} C={C:.9e} delta={delta:.9e} "
              f"approach={base.normal_approach_speed_m_s:+.6e}")
        print(f"   {'mode':<8}{'dF/dq':>14}{'FD dC/dq':>14}{'FD ddelta/dq':>15}"
              f"{'pred(2/3)(d/F-dC/C)':>21}{'FD dapproach':>15}"
              f"{'FD ddzds':>13}{'FD dnormal_y':>14}")
        for k, col in enumerate(modes):
            h = 1e-7 * max(1.0, abs(q[col]))
            qp = q.copy(); qm = q.copy()
            qp[col] += h; qm[col] -= h
            pp = probe(dyn, t_s, qp, v, index)
            pm = probe(dyn, t_s, qm, v, index)
            fd_c = (pp.geometry.stiffness_n_m_1p5 - pm.geometry.stiffness_n_m_1p5) / (2 * h)
            fd_d = (pp.geometry.penetration_m - pm.geometry.penetration_m) / (2 * h)
            fd_a = (pp.normal_approach_speed_m_s - pm.normal_approach_speed_m_s) / (2 * h)
            fd_z = (pp.geometry.rail_dz_ds - pm.geometry.rail_dz_ds) / (2 * h)
            fd_n = (pp.geometry.normal_y - pm.geometry.normal_y) / (2 * h)
            dF = parts.normal_force_n[k]
            pred = (2.0 / 3.0) * delta * (dF / F - fd_c / C)
            print(f"   {MODES[k]:<8}{dF:>14.6e}{fd_c:>14.6e}{fd_d:>15.6e}"
                  f"{pred:>21.6e}{fd_a:>15.6e}{fd_z:>13.3e}{fd_n:>14.4e}")
        # how much of dnormal does the ratio trick cost?
        elastic_slope = 1.5 * F / delta
        print(f"   elastic_slope={elastic_slope:.6e}  "
              f"rate_slope={3e7 * np.sqrt(delta):.6e}  "
              f"damping={base.normal_damping_n:+.4f}")


if __name__ == "__main__":
    main()
