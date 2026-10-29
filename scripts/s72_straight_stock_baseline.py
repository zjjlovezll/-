"""Seat and run the RIGID straight turnout through its frog zone on the stock profile only.

Why this script exists: round 12 tried to reach the frog on the *curved* station table
(`scratch/s30/case_diverging_gauge.json`), whose right rail splices five different section
families (`jbg` -> `qjbg` -> ... -> `cxg`) with disjoint lateral spans, and the seat died with
``ProfileError: adjacent profiles have no lateral overlap``.  That failure is a property of the
curved table, not of the straight route: the straight case built in round 12
(``scratch/s64/case_gap.json``) rewrites every through-route station to the plain stock section, so
its stock body is a single family over 30.0-116.5 m and has no splice at all.

So this run is the **zero-lowering baseline**: the vehicle traverses 95 m -> beyond the frog
(103.28-116.44 m in the curved table) with nothing but the stock surface.  Any load rise measured
here is *not* the frog lowering; it is the reference that a frog body would have to beat.

The seat is asked for at 95 m so the four axles (105, 102.5, 87.5, 85 m) all lie inside the stock
body (30.0-116.5 m).  Print per-wheel loads, gates, and the lateral ledger; write a small JSON.

Recompute::

    cd F:/ai道岔状态反演辨识/Velch
    PYTHONPATH=src python -X utf8 scripts/s72_straight_stock_baseline.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat, simulate_vehicle

HERE = Path(__file__).resolve().parents[1]
DEFAULT_CASE = Path("../scratch/s64/case_gap.json")
EVEN_SHARE_N = 59_662.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default=str(DEFAULT_CASE))
    parser.add_argument("--start", type=float, default=95.0)
    parser.add_argument("--duration", type=float, default=0.35)
    parser.add_argument("--output-step", type=float, default=1e-3)
    parser.add_argument("--out", default="../scratch/s72")
    options = parser.parse_args()

    out = Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "case_stock_baseline.json"
    raw = json.loads(Path(options.case).read_text(encoding="utf-8"))
    raw["case_id"] = f"{raw['case_id']}_stock_from{options.start:g}"
    raw["run"].update(
        x_start_m=float(options.start),
        seat_x_start_m=float(options.start),
        duration_s=float(options.duration),
        output_step_s=float(options.output_step),
        max_solver_step_s=min(float(raw["run"].get("max_solver_step_s", 1e-3)), 1e-3),
    )
    raw.pop("initial_state", None)
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    case = load_vehicle_case(target)
    dynamics = VehicleDynamics(case)
    print(f"coordinates {dynamics.dimension}, rails {len(case.rails)}, "
          f"bodies/rail {[len(rail.bodies) for rail in case.rails]}")
    for rail in case.rails:
        if rail.id.endswith("right"):
            print(f"  {rail.id}: " + ", ".join(
                f"{body.id} {body.series.lowest_m:.3f}..{body.series.highest_m:.3f}" for body in rail.bodies))
            break

    q0 = np.zeros(dynamics.dimension)
    velocity = np.zeros(dynamics.dimension)
    for body in dynamics.topology.bodies:
        if "spin" not in body.dof:
            continue
        velocity[dynamics.topology.require(body.id, "spin")] = (
            float(case.vehicle.travel_speed_m_s) / float(case.vehicle.nominal_wheel_radius_m)
        )
    print(f"travel speed {float(case.vehicle.travel_speed_m_s):.4f} m/s "
          f"({float(case.vehicle.travel_speed_m_s) * 3.6:.2f} km/h)")
    seated, residual = _seat(case, dynamics, q0, velocity)
    print(f"seat residual {residual:.3e} N")

    result = simulate_vehicle(case, contact_workers=1)
    summary = result.get("summary") if isinstance(result, dict) else getattr(result, "summary", None)
    print("status:", summary.get("status") if isinstance(summary, dict) else summary)
    print("gates:", summary.get("gates") if isinstance(summary, dict) else "?")

    contacts = result["contacts"] if isinstance(result, dict) else result.contacts
    times = result["times_s"] if isinstance(result, dict) else result.times_s
    last = contacts[-1]
    loads, levers = {}, {}
    for rail_id, response in last.items():
        if response is None or getattr(response, "geometry", None) is None:
            continue
        loads[rail_id] = float(response.normal_force_n)
        levers[rail_id] = float(response.geometry.lever_y_m)
    peak = {rail_id: max(
        float(entry[rail_id].normal_force_n) if entry.get(rail_id) is not None
        and getattr(entry[rail_id], "geometry", None) is not None else 0.0
        for entry in contacts)
        for rail_id in loads}
    print(f"{'rail':<16}{'N last (kN)':>12}{'x share':>9}{'lever_y':>10}{'peak (kN)':>11}")
    for rail_id in sorted(loads):
        print(f"{rail_id:<16}{loads[rail_id]/1e3:12.3f}{loads[rail_id]/EVEN_SHARE_N:9.3f}"
              f"{levers[rail_id]:+10.4f}{peak[rail_id]/1e3:11.3f}")
    print(f"travelled {float(times[-1]) * float(case.vehicle.travel_speed_m_s):.3f} m in {float(times[-1]):.3f} s")

    (out / "stock_baseline.json").write_text(json.dumps({
        "case": str(target),
        "coordinates": dynamics.dimension,
        "seat_residual_n": float(residual),
        "status": summary.get("status") if isinstance(summary, dict) else None,
        "gates": summary.get("gates") if isinstance(summary, dict) else None,
        "last_loads_n": loads,
        "last_lever_y_m": levers,
        "peak_loads_n": peak,
        "even_share_n": EVEN_SHARE_N,
    }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
