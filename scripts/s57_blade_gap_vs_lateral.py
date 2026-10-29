"""Map where the blade starts carrying load in (mileage, wheelset lateral displacement).

Round 219 withdrew the mileage-only blade-onset criterion: from 52 m the blade picks up load at
68.152 m, from 62 / 66.5 m it never touches.  The stated reason is that the wheel surface height at the
blade's lateral position is set by the wheelset's lateral displacement, so the crossing mileage is a
function of `q[y]`, not a constant.

This measures that surface directly, without integrating a trajectory: seat the vehicle on the straight
approach, place axle 1 at a given mileage by choosing `t`, shift `wheelset1` laterally, and read whether
the blade body carries load.  The boundary is the two-dimensional criterion the null test needs.

    PYTHONPATH=src python -X utf8 scripts/s57_blade_gap_vs_lateral.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
CASE = HERE.parent / "scratch" / "s52" / "case_two_body_switch.json"
TIP_M = 60.95
ONSET_FROM_TIP_M = 7.208
ONSET_AT_M = TIP_M + ONSET_FROM_TIP_M
AXLE1_OFFSET_M = 10.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--x-start", type=float, default=52.0)
    parser.add_argument("--seat-at", type=float, default=45.0)
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    parser.add_argument("--mileage-lo", type=float, default=67.2)
    parser.add_argument("--mileage-hi", type=float, default=68.8)
    parser.add_argument("--mileage-step", type=float, default=0.2)
    parser.add_argument("--shift-mm", type=float, nargs="+", default=[-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0])
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
    target = HERE.parent / "scratch" / "s57" / "case.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw), encoding="utf-8")

    case = load_vehicle_case(target)
    dynamics = VehicleDynamics(case)
    y_index = int(dynamics.topology.require("wheelset1", "y"))
    q = np.zeros(dynamics.dimension, dtype=float)
    v = np.zeros(dynamics.dimension, dtype=float)
    seated, residual = _seat(case, dynamics, q, v)
    print(f"seat residual {residual:.3e} N   x_start {args.x_start:.1f} m   {args.speed_kmh:.1f} km/h")
    print(f"criterion mileage (mileage-only form): {ONSET_AT_M:.3f} m\n")

    recorded: dict[str, list[tuple[str, float]]] = {}

    def record(t_s, rail_id, bodies) -> None:
        if rail_id.startswith("axle1_"):
            recorded[rail_id] = [(body_id, float(force)) for body_id, force in bodies]

    saved = solver_module.BODY_CONTACT_HOOK
    solver_module.BODY_CONTACT_HOOK = record
    rows = []
    try:
        mileages = np.arange(args.mileage_lo, args.mileage_hi + 1.0e-9, args.mileage_step)
        for mileage in mileages:
            t_s = (float(mileage) - AXLE1_OFFSET_M - args.x_start) / speed
            for shift_mm in args.shift_mm:
                state = seated.copy()
                state[y_index] += shift_mm * 1.0e-3
                recorded.clear()
                dynamics.evaluate(float(t_s), state, v)
                right = recorded.get("axle1_right", [])
                blade = sum(force for body_id, force in right if body_id.endswith("blade"))
                stock = sum(force for body_id, force in right if body_id.endswith("stock"))
                rows.append(
                    {
                        "mileage_m": float(mileage),
                        "shift_mm": float(shift_mm),
                        "blade_kn": blade / 1.0e3,
                        "stock_kn": stock / 1.0e3,
                    }
                )
    finally:
        solver_module.BODY_CONTACT_HOOK = saved
    dynamics.close()

    print(f"{'mileage':>8}  " + "  ".join(f"{s:+5.1f}mm" for s in args.shift_mm))
    for mileage in sorted({row['mileage_m'] for row in rows}):
        values = [row for row in rows if row["mileage_m"] == mileage]
        cells = "  ".join(f"{row['blade_kn']:6.2f}" for row in values)
        print(f"{mileage:8.2f}  {cells}")

    boundary = []
    for mileage in sorted({row['mileage_m'] for row in rows}):
        values = [row for row in rows if row["mileage_m"] == mileage]
        touching = [row["shift_mm"] for row in values if row["blade_kn"] > 0.0]
        boundary.append({"mileage_m": mileage, "touch_shifts_mm": touching})
    print("\nshifts (mm) that bring the blade into load:")
    for entry in boundary:
        print(f"  {entry['mileage_m']:8.2f}   {entry['touch_shifts_mm']}")

    out = HERE.parent / "scratch" / "s57" / "blade_gap.json"
    out.write_text(json.dumps({"rows": rows, "boundary": boundary}, indent=1), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
