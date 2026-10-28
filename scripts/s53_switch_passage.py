"""Can the vehicle cross the two-body switch zone, and does it stay on the stock rail?

The two-body case (`scripts/s52_switch_two_body.py`) puts the blade 23 mm down at its tip and brings it
up to full height 7.3 m later.  The claim to test is narrow and falsifiable:

* the wheel runs on the **stock** rail the whole way, so its vertical motion follows the stock surface;
* the blade only starts carrying load once it has risen into the clearance (tens of micrometres);
* nothing here is an irregularity -- any wheel vertical motion is the design geometry itself.

Run::

    PYTHONPATH=src python -X utf8 scripts/s53_switch_passage.py --x-start 52 --duration 0.05
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
CASE = HERE.parent / "scratch" / "s52" / "case_two_body_switch.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, default=CASE)
    parser.add_argument("--x-start", type=float, default=52.0)
    parser.add_argument("--seat-at", type=float, default=45.0)
    parser.add_argument("--duration", type=float, default=0.05)
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    args = parser.parse_args()

    from velch.solver import SimulationFailure
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import simulate_vehicle

    raw = json.loads(args.case.read_text(encoding="utf-8"))
    raw["run"].update(
        {
            "x_start_m": args.x_start,
            "seat_x_start_m": args.seat_at,
            "duration_s": args.duration,
            "output_step_s": min(5.0e-4, args.duration / 20.0),
            "max_solver_step_s": 1.0e-4,
            "method": "BDF",
            "jacobian": "analytic",
        }
    )
    raw["vehicle"]["travel_speed_m_s"] = args.speed_kmh / 3.6
    raw.pop("initial_state", None)
    target = HERE.parent / "scratch" / "s53" / "case.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw), encoding="utf-8")

    case = load_vehicle_case(target)
    print(f"case      x_start {args.x_start:.1f} m   seat {args.seat_at:.1f} m   "
          f"{args.speed_kmh:.1f} km/h   {args.duration:.3f} s")
    print(f"track     {case.track_kind}   rails {len(case.rails)}   "
          f"bodies {sum(len(r.bodies) for r in case.rails)}")
    try:
        result = simulate_vehicle(case)
    except SimulationFailure as error:
        print(f"\nFAILED    {error}")
        return 2

    summary = result.summary or {}
    frames = len(result.times_s)
    print(f"\nstatus    {summary.get('status')}   frames {frames}")
    gates = summary.get("gates") or {}
    failed = [name for name, ok in gates.items() if not ok]
    print(f"gates     {len(gates) - len(failed)}/{len(gates)}"
          + (f"   failing {failed}" if failed else ""))
    peak = summary.get("max_penetration_m")
    if peak is not None:
        print(f"penetration  max {float(np.max(np.asarray(peak, dtype=float))) * 1.0e6:.2f} um")
    travelled = float(result.times_s[-1]) * args.speed_kmh / 3.6
    print(f"travelled {travelled:.2f} m   front axle "
          f"{args.x_start + travelled + 10.0:.2f} m")

    print("\nlast frame, per contact body:")
    for rail_id, contacts in sorted(result.contacts[-1].items()):
        # `contacts` is the ContactResponse itself for this rail in this release.
        for body_id, contact in (("", contacts),):
            geometry = contact.geometry
            if geometry is None:
                continue
            print(f"  {rail_id:14s} {body_id:12s} N {contact.normal_force_n / 1.0e3:8.2f} kN"
                  f"   pen {geometry.penetration_m * 1.0e6:7.2f} um"
                  f"   lever_y {geometry.lever_y_m:+.5f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
