# -*- coding: utf-8 -*-
"""B5: can the analytic Jacobian act as a contact-event detector?

A contact transition (tread -> flange, body switch, contact loss) changes which
surface carries the load, so dN/dq jumps even though q is continuous.  If that
jump is visible in the Jacobian, then |J(t+dt) - J(t)| is an event indicator that
costs one Jacobian instead of a dense force series.

We sweep the first axle's lateral DOF across the tread/flange transition at a
fixed pose and report, per step: contact normal force, contact lateral position,
the set of selected surfaces, and the Frobenius norm of the analytic Jacobian.
"""
import json
import math
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

CASE = HERE / "case_frog_N_strip05.json"


def main() -> int:
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import _static_vertical_equilibrium, VehicleDynamics
    from velch.jacobian import JacobianAssembler

    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    q, residual = _static_vertical_equilibrium(case, dynamics, q, v)
    print(f"static equilibrium: residual {residual:.3e} N")

    assembler = JacobianAssembler(dynamics)
    n = dynamics.dimension
    rows = []
    previous = None
    for shift_mm in np.arange(-2.0, 12.01, 1.0):
        trial = q.copy()
        trial[0] += shift_mm * 1e-3            # axle 1 lateral
        force, contacts = dynamics.evaluate(0.0, trial, v)
        response = contacts[case.rails[0].id]
        jac = assembler.full(0.0, trial, v)
        norm = float(np.linalg.norm(jac))
        delta = 0.0 if previous is None else float(np.linalg.norm(jac - previous))
        previous = jac
        geometry = response.geometry
        label = "none" if geometry is None else ",".join(
            getattr(geometry, "selected_ids", ()) or ())
        rows.append({
            "shift_mm": float(shift_mm),
            "normal_n": float(response.normal_force_n),
            "contact_y_mm": float(geometry.y_m * 1e3) if geometry else float("nan"),
            "pen_um": float(geometry.penetration_m * 1e6) if geometry else 0.0,
            "selected": label,
            "jacobian_norm": norm,
            "jacobian_jump": delta,
        })

    print(f"{'shift':>6s} {'N kN':>8s} {'y mm':>8s} {'pen um':>8s} {'|J|':>9s} "
          f"{'|dJ|':>9s} surfaces")
    for row in rows:
        print(f"{row['shift_mm']:6.1f} {row['normal_n']/1e3:8.3f} {row['contact_y_mm']:8.2f} "
              f"{row['pen_um']:8.2f} {row['jacobian_norm']:9.2f} {row['jacobian_jump']:9.2f} "
              f"{row['selected']}")

    jumps = [row for row in rows if row["jacobian_jump"] > 0.0]
    if jumps:
        peak = max(jumps, key=lambda row: row["jacobian_jump"])
        print(f"\nlargest jump: {peak['jacobian_jump']:.3f} at shift {peak['shift_mm']:+.1f} mm "
              f"(|J| {peak['jacobian_norm']:.2f})")
        base = rows[0]["jacobian_norm"]
        print(f"|J| range over sweep: {min(r['jacobian_norm'] for r in rows):.2f} .. "
              f"{max(r['jacobian_norm'] for r in rows):.2f} (base {base:.2f})")

    (HERE / "b5_jacobian_events.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
