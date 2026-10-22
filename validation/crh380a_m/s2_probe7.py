"""Check the *model* normal-force gradient at t=0.70, per rail, against the
partials the Jacobian consumes.  If the two disagree, the defect is in the
partials; if they agree, it is in the assembly."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from velch.jacobian import JacobianAssembler                  # noqa: E402
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


def forces(dyn, t_s, q, v):
    dyn.contact_partials = True
    dyn.evaluate(t_s, q, v)
    out = {}
    for index, rail in enumerate(dyn.case.rails):
        for response in dyn.body_contacts.get(rail.id, ()):
            if not response.active or response.geometry is None:
                continue
            out[(index, response.body.id if hasattr(response, "body") else 0)] = (
                response.normal_force_n, response.geometry,
                response.longitudinal_force_n, response.lateral_tangent_force_n,
                response.normal_elastic_n, response.normal_damping_n,
                response.normal_approach_speed_m_s, response.geometry.rail_dz_ds)
    return out


def main() -> None:
    case = load_vehicle_case(SOURCE)
    dyn, q, v = _equilibrated(case)
    asm = JacobianAssembler(dyn)
    n = dyn.dimension
    for t_s in (0.70, 0.45, 0.0):
        base = forces(dyn, t_s, q, v)
        print(f"\n=== t={t_s:.2f}  contacts={len(base)}")
        for (index, _bid), item in base.items():
            force0, geom0, tx0, tl0, el0, dp0, ap0, dzds0 = item
            rail = case.rails[index]
            wh = 5 * rail.axle_index
            modes = (wh, wh + 1, wh + 2, 35 + 2 * index, 35 + 2 * index + 1)
            parts = geom0.partials
            print(f" rail{index} N={force0:9.3f} el={el0:9.3f} damp={dp0:+9.3f} "
                  f"approach={ap0:+.3e} dzds={dzds0:+.3e} C={geom0.stiffness_n_m_1p5:.6e} "
                  f"R*={geom0.radius_star_m:.6f} pen={geom0.penetration_m * 1e6:7.3f}um")
            for k, col in enumerate(modes):
                h = 1e-7 * max(1.0, abs(q[col]))
                qp = q.copy(); qm = q.copy()
                qp[col] += h; qm[col] -= h
                fp = forces(dyn, t_s, qp, v)[(index, _bid)][0]
                fm = forces(dyn, t_s, qm, v)[(index, _bid)][0]
                fd = (fp - fm) / (2.0 * h)
                ana = parts.normal_force_n[k]
                rel = abs(ana - fd) / max(abs(fd), 1e-30)
                flag = "  <-- MISMATCH" if rel > 1e-6 else ""
                print(f"   mode{k} col{col:2d} ana={ana:+.9e} fd={fd:+.9e} "
                      f"rel={rel:.2e}{flag}")
            # lever partials
            for k, col in enumerate(modes):
                h = 1e-6 * max(1.0, abs(q[col]))
                qp = q.copy(); qm = q.copy()
                qp[col] += h; qm[col] -= h
                gp = forces(dyn, t_s, qp, v)[(index, _bid)][1]
                gm = forces(dyn, t_s, qm, v)[(index, _bid)][1]
                fdl = (gp.lever_y_m - gm.lever_y_m) / (2.0 * h)
                fdz = (gp.lever_z_m - gm.lever_z_m) / (2.0 * h)
                rel = abs(parts.lever_y_m[k] - fdl) / max(abs(fdl), 1e-30)
                relz = abs(parts.lever_z_m[k] - fdz) / max(abs(fdz), 1e-30)
                if rel > 1e-5 or relz > 1e-4:
                    print(f"   lever mode{k} col{col:2d} ana=({parts.lever_y_m[k]:+.6e},"
                          f"{parts.lever_z_m[k]:+.6e}) fd=({fdl:+.6e},{fdz:+.6e}) "
                          f"rel={rel:.1e}/{relz:.1e}")


if __name__ == "__main__":
    main()
