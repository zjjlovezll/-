"""Which spring, if any, resists a lateral shift of the wheelset at the seat?

Round 246 left +238 N of net lateral force after the 4x wheel sampling, and round 247's joint seat
moved the wheelset by only +0.3 um while the net force stayed +236.88 N.  If a lateral spring were
acting on the wheelset, 238 N would be taken out by 238 / k.  Two candidates explain a near-zero
response:

  * the wheelset ``y`` row carries no spring at all (the primary spring pair may connect the bogie
    to the axle box, leaving the wheelset laterally free) -- then the seat has no way to zero the
    force and the vehicle walks sideways for as long as the force lasts;
  * the joint seat did not actually include ``y`` -- a code defect, not physics.

This probe separates them by measurement only: seat once, then shift ``wheelset1.y`` by small steps
*without* re-seating, and read the net lateral force of axle 1 and the two patch loads.  The local
slope ``dFy/dy`` is the answer:

    |dFy/dy| ~ 3e7 N/m   -> a 3e7 N/m primary spring acts on the wheelset
    |dFy/dy| ~ 3e6 N/m   -> only the contact geometry resists; the wheelset is laterally free

    PYTHONPATH=src python -X utf8 scripts/s109_lateral_stiffness.py [--write]
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat, _settle_modal_coordinates

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s109"
SPEED_M_S = 80.0 / 3.6
ROLL_RADIUS_M = 0.43
STEPS_MM = (-0.20, -0.05, -0.01, 0.0, 0.01, 0.05, 0.20)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    try:
        v = np.asarray(case.initial_v, dtype=float)
        for index in range(1, 5):
            v[dynamics.topology.require(f"wheelset{index}", "spin")] = SPEED_M_S / ROLL_RADIUS_M
        q = np.asarray(case.initial_q, dtype=float)
        q, residual = _seat(case, dynamics, q, v)
        q = np.asarray(q, dtype=float)
        for _round in range(2):
            q = _settle_modal_coordinates(dynamics, q, v)
            q, residual = _seat(case, dynamics, q, v)
            q = np.asarray(q, dtype=float)

        y_index = dynamics.topology.require("wheelset1", "y")
        rows = []
        for step in STEPS_MM:
            trial = q.copy()
            trial[y_index] += step * 1e-3
            _, contacts = dynamics.evaluate(0.0, trial, v)
            left = contacts["axle1_left"]
            right = contacts["axle1_right"]
            rows.append({
                "dy_mm": step,
                "net_lateral_n": float(left.wheel_force_y_n + right.wheel_force_y_n),
                "left_n": float(left.normal_force_n),
                "right_n": float(right.normal_force_n),
                "left_active": bool(left.active),
                "right_active": bool(right.active),
            })
            print(f"  dy {step:+7.3f} mm   net Fy {rows[-1]['net_lateral_n']:+9.2f} N"
                  f"   N {rows[-1]['left_n']:9.1f} / {rows[-1]['right_n']:9.1f} N"
                  f"   active {rows[-1]['left_active']}/{rows[-1]['right_active']}")

        # Local slope from the innermost pair, where no contact is lost, and from a global fit.
        inner = [row for row in rows if abs(row["dy_mm"]) <= 0.05]
        dy = np.array([row["dy_mm"] for row in inner]) * 1e-3
        force = np.array([row["net_lateral_n"] for row in inner])
        slope_inner = float(np.polyfit(dy, force, 1)[0]) if len(dy) >= 2 else float("nan")
        all_dy = np.array([row["dy_mm"] for row in rows]) * 1e-3
        all_force = np.array([row["net_lateral_n"] for row in rows])
        slope_all = float(np.polyfit(all_dy, all_force, 1)[0])

        at_zero = next(row for row in rows if row["dy_mm"] == 0.0)
        print()
        print(f"seated net lateral      {at_zero['net_lateral_n']:+.2f} N")
        print(f"dFy/dy (inner +-0.05)   {slope_inner/1e6:+.3f} MN/m")
        print(f"dFy/dy (all +-0.20)     {slope_all/1e6:+.3f} MN/m")
        verdict = ("a primary lateral spring resists the shift"
                   if abs(slope_inner) > 1.5e7 else
                   "only the contact geometry resists: the wheelset is laterally free")
        print(f"VERDICT: {verdict}")

        if args.write:
            OUT.mkdir(parents=True, exist_ok=True)
            payload = {"rows": rows, "slope_inner_n_per_m": slope_inner,
                       "slope_all_n_per_m": slope_all,
                       "seat_residual_n": residual, "verdict": verdict}
            (OUT / "lateral_stiffness.json").write_text(
                json.dumps(payload, indent=1, ensure_ascii=False) + chr(10), encoding="utf-8")
            print(f"report -> {OUT / 'lateral_stiffness.json'}")
    finally:
        dynamics.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
