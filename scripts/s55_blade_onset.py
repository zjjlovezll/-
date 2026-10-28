"""Where does the blade start carrying load?  Read it per body, not per rail.

The two-body switch zone (`scripts/s52_switch_two_body.py`) keeps a stock rail and a blade side by side.
`evaluate` merges them into one response per rail, which is what the wheel feels, so the blade's share is
invisible in `history.csv`.  `velch.vehicle_solver.BODY_CONTACT_HOOK` exists for exactly this read.

**Pre-registered criterion** (from the design table in `reports/turnout_lowering_2026-10-29/lowering.json`,
23 mm at the tip falling to 0 at 7.304 m): the blade can only touch once the design lowering is smaller
than the static penetration 65.47 um, i.e. at 7.304 - (0.06547/0.5)*0.735 = **7.208 m from the tip**, which
for this case is **68.16 m**.  The blade's first non-zero force must therefore appear at 68.16 +- 0.20 m.

Run::

    PYTHONPATH=src python -X utf8 scripts/s55_blade_onset.py --x-start 52 --duration 0.32
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CASE = HERE.parent / "scratch" / "s52" / "case_two_body_switch.json"
TIP_M = 60.95
RISE_ZERO_M = 7.304
STATIC_PENETRATION_M = 65.47e-6
SLOPE_MM_PER_M = 0.5 / (RISE_ZERO_M - 6.569)
ONSET_FROM_TIP_M = RISE_ZERO_M - (STATIC_PENETRATION_M * 1.0e3) / SLOPE_MM_PER_M


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, default=CASE)
    parser.add_argument("--x-start", type=float, default=52.0)
    parser.add_argument("--seat-at", type=float, default=45.0)
    parser.add_argument("--duration", type=float, default=0.32)
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    args = parser.parse_args()

    from velch import vehicle_solver as solver_module
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import simulate_vehicle

    raw = json.loads(args.case.read_text(encoding="utf-8"))
    raw["run"].update(
        {
            "x_start_m": args.x_start,
            "seat_x_start_m": args.seat_at,
            "duration_s": args.duration,
            "output_step_s": min(5.0e-4, args.duration / 40.0),
            "max_solver_step_s": 1.0e-4,
            "method": "BDF",
            "jacobian": "analytic",
        }
    )
    raw["vehicle"]["travel_speed_m_s"] = args.speed_kmh / 3.6
    raw.pop("initial_state", None)
    target = HERE.parent / "scratch" / "s55" / "case.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw), encoding="utf-8")

    case = load_vehicle_case(target)
    speed = args.speed_kmh / 3.6
    onset_m = TIP_M + ONSET_FROM_TIP_M
    print(f"case      x_start {args.x_start:.1f} m   {args.speed_kmh:.1f} km/h   {args.duration:.3f} s")
    print(f"criterion blade touches at {onset_m:.2f} m +- 0.20 m "
          f"(lowering = {STATIC_PENETRATION_M * 1.0e6:.2f} um at {ONSET_FROM_TIP_M:.3f} m from the tip)")
    print()

    rows: list[tuple[float, dict[str, float]]] = []

    def record(t_s, rail_id, bodies) -> None:
        if not rail_id.startswith("axle1_"):
            return
        for body_id, force in bodies:
            if body_id.endswith("blade"):
                rows.append((float(t_s), {"rail": rail_id, "force": force}))

    saved = solver_module.BODY_CONTACT_HOOK
    solver_module.BODY_CONTACT_HOOK = record
    try:
        result = simulate_vehicle(case)
    finally:
        solver_module.BODY_CONTACT_HOOK = saved

    summary = result.summary or {}
    print(f"status    {summary.get('status')}   frames {len(result.times_s)}   "
          f"gates {sum(1 for ok in (summary.get('gates') or {}).values() if ok)}"
          f"/{len(summary.get('gates') or {})}")
    print()

    first = None
    for t_s, entry in rows:
        if entry["force"] > 0.0:
            first = (t_s, entry)
            break
    if first is None:
        print(f"blade never carried load in {rows[-1][0] if rows else 0.0:.3f} s "
              f"-> the run stopped before {onset_m:.2f} m")
        return 2

    t_onset, entry = first
    axle_m = args.x_start + 10.0 + t_onset * speed
    error = axle_m - onset_m
    print(f"first blade load  t {t_onset:.3f} s   axle1 at {axle_m:.3f} m   "
          f"F {entry['force'] / 1.0e3:.3f} kN")
    print(f"criterion error   {error:+.3f} m   ({'PASS' if abs(error) <= 0.20 else 'FAIL'} at +- 0.20 m)")
    print()
    print("  axle1 at (m)   blade force (kN)")
    for t_s, sample in rows[:: max(1, len(rows) // 14)]:
        print(f"  {args.x_start + 10.0 + t_s * speed:11.2f}   {sample['force'] / 1.0e3:14.3f}")
    return 0 if abs(error) <= 0.20 else 2


if __name__ == "__main__":
    raise SystemExit(main())
