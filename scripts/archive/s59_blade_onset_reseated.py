"""Blade onset with the vertical state in equilibrium at every point -- the corrected 2-D boundary.

`scripts/s57_blade_gap_vs_lateral.py` placed axle 1 at a mileage but kept the *seated* vertical state,
and the right wheel then had **no contact at all** from 67.90 to 68.60 m (`stock 0.00 kN`), because the
rail surface rises along the switch zone and the wheel was left floating.  Its "first blade load" was
therefore a surface-height crossover, not a contact boundary.

Here the vertical coordinates are re-solved at every (mileage, lateral shift) before the blade force is
read, so the wheel is genuinely loaded and the boundary is the one the criterion needs.

    PYTHONPATH=src python -X utf8 scripts/s59_blade_onset_reseated.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parents[1]
CASE = HERE.parent / "scratch" / "s52" / "case_two_body_switch.json"
TIP_M = 60.95
ONSET_FROM_TIP_M = 7.208
ONSET_AT_M = TIP_M + ONSET_FROM_TIP_M
AXLE1_OFFSET_M = 10.0
EVEN_SHARE_N = 59_662.0


def vertical_indices(dynamics) -> list[int]:
    topology = dynamics.topology
    indices = []
    for body in topology.bodies:
        dofs = list(getattr(body, "dof", ()) or ())
        if "z" in dofs:
            indices.append(int(topology.require(body.id, "z")))
    if str(getattr(dynamics.track, "kind", "")) == "local_compliant":
        base = int(topology.body_dimension)
        count = int(dynamics.track.dimension) // 2
        indices.extend(base + 2 * i + 1 for i in range(count))
    return indices


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--x-start", type=float, default=52.0)
    parser.add_argument("--seat-at", type=float, default=45.0)
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    parser.add_argument("--mileage-lo", type=float, default=67.6)
    parser.add_argument("--mileage-hi", type=float, default=68.9)
    parser.add_argument("--mileage-step", type=float, default=0.1)
    parser.add_argument("--shift-mm", type=float, nargs="+", default=[-1.0, 0.0, 0.5, 1.0, 2.0])
    args = parser.parse_args()

    from velch import vehicle_solver as solver_module
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics, _seat

    raw = json.loads(CASE.read_text(encoding="utf-8"))
    raw["run"].update(
        {
            "x_start_m": args.x_start,
            "seat_x_start_m": args.seat_at,
            "duration_s": 0.02,
            "output_step_s": 0.01,
            "max_solver_step_s": 1.0e-4,
            "method": "BDF",
            "jacobian": "analytic",
        }
    )
    speed = args.speed_kmh / 3.6
    raw["vehicle"]["travel_speed_m_s"] = speed
    raw.pop("initial_state", None)
    target = HERE.parent / "scratch" / "s59" / "case.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw), encoding="utf-8")

    case = load_vehicle_case(target)
    dynamics = VehicleDynamics(case)
    y_index = int(dynamics.topology.require("wheelset1", "y"))
    z_rows = vertical_indices(dynamics)
    q = np.zeros(dynamics.dimension, dtype=float)
    v = np.zeros(dynamics.dimension, dtype=float)
    seated, residual = _seat(case, dynamics, q, v)
    print(f"seat residual {residual:.3e} N at {args.x_start:.1f} m   vertical rows {len(z_rows)}")

    recorded: dict[str, list[tuple[str, float]]] = {}

    def record(t_s, rail_id, bodies) -> None:
        if rail_id.startswith("axle1_"):
            recorded[rail_id] = [(body_id, float(force)) for body_id, force in bodies]

    saved = solver_module.BODY_CONTACT_HOOK
    solver_module.BODY_CONTACT_HOOK = record

    def forces_at(t_s: float, state: np.ndarray) -> tuple[float, float]:
        recorded.clear()
        dynamics.evaluate(float(t_s), state, v)
        right = recorded.get("axle1_right", [])
        blade = sum(force for body_id, force in right if body_id.endswith("blade"))
        stock = sum(force for body_id, force in right if body_id.endswith("stock"))
        return blade, stock

    def reseat(t_s: float, state: np.ndarray) -> tuple[np.ndarray, float]:
        def residual_fn(values: np.ndarray) -> np.ndarray:
            trial = state.copy()
            trial[z_rows] = values
            force, _contacts = dynamics.evaluate(float(t_s), trial, v)
            return np.asarray(force, dtype=float)[z_rows] / 1.0e5

        guess = state[z_rows].copy()
        solution = least_squares(residual_fn, guess, method="trf", xtol=1e-12, ftol=1e-12, gtol=1e-12,
                                 max_nfev=200)
        solved = state.copy()
        solved[z_rows] = solution.x
        return solved, float(np.max(np.abs(residual_fn(solution.x))))

    rows = []
    try:
        for mileage in np.arange(args.mileage_lo, args.mileage_hi + 1.0e-9, args.mileage_step):
            t_s = (float(mileage) - AXLE1_OFFSET_M - args.x_start) / speed
            for shift_mm in args.shift_mm:
                state = seated.copy()
                state[y_index] += shift_mm * 1.0e-3
                state, residual_z = reseat(t_s, state)
                blade, stock = forces_at(t_s, state)
                rows.append(
                    {
                        "mileage_m": float(mileage),
                        "shift_mm": float(shift_mm),
                        "blade_kn": blade / 1.0e3,
                        "stock_kn": stock / 1.0e3,
                        "wheel_kn": (blade + stock) / 1.0e3,
                        "reseat_residual": residual_z,
                    }
                )
    finally:
        solver_module.BODY_CONTACT_HOOK = saved
    dynamics.close()

    print(f"\n{'mileage':>8}  " + "  ".join(f"{s:+5.1f}mm" for s in args.shift_mm) + "   (blade kN)")
    for mileage in sorted({row['mileage_m'] for row in rows}):
        values = [row for row in rows if row["mileage_m"] == mileage]
        print(f"{mileage:8.2f}  " + "  ".join(f"{row['blade_kn']:6.2f}" for row in values))
    print(f"\n{'mileage':>8}  wheel total kN at shift 0.0  (even share {EVEN_SHARE_N / 1.0e3:.1f} kN)")
    for row in rows:
        if abs(row["shift_mm"]) < 1.0e-9:
            print(f"{row['mileage_m']:8.2f}  wheel {row['wheel_kn']:8.2f}  stock {row['stock_kn']:8.2f}  "
                  f"blade {row['blade_kn']:7.2f}  residual {row['reseat_residual']:.2e}")

    boundary = []
    for mileage in sorted({row['mileage_m'] for row in rows}):
        values = [row for row in rows if row["mileage_m"] == mileage]
        boundary.append(
            {
                "mileage_m": mileage,
                "touch_shifts_mm": [row["shift_mm"] for row in values if row["blade_kn"] > 0.0],
            }
        )
    print("\nshifts (mm) that load the blade:")
    for entry in boundary:
        print(f"  {entry['mileage_m']:8.2f}   {entry['touch_shifts_mm']}")

    out = HERE.parent / "scratch" / "s59" / "boundary.json"
    out.write_text(json.dumps({"rows": rows, "boundary": boundary, "criterion_m": ONSET_AT_M}, indent=1),
                   encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
