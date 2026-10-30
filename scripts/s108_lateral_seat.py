"""Does solving the lateral equilibrium remove the +736 N that walks the vehicle sideways?

Round 246 established the mechanism: after the vertical/modal seat the flexible tread tilts
+0.024782 on the left and -0.021744 on the right, so the seated state carries +736.5 N
(+184 N per axle) and the vehicle translates +0.73 mm in 0.40 s.  The asymmetry converges (tested
0..8 outer rounds: +668 N -> +737.8 N), so it is an equilibrium offset, not an unfinished
initialisation: the vehicle is standing to one side of the position where its own lateral force
vanishes.

Gates, written before the first run:

    G1  vertical seat residual <= 1e-5 N and 8/8 wheels in [0.625, 1.6] x share
    G2  |net lateral force per axle| <= 20 N after the lateral seat
    G3  |tilt_left + tilt_right| <= 1.0e-3 (i.e. the two tilts are equal to 4 % of 0.0246)
    G4  the seat stays cheap: wall time of the whole seat <= 60 s

A run that fails G2 or G3 is reported as failing; nothing here changes a tolerance.

    PYTHONPATH=src python -X utf8 scripts/s108_lateral_seat.py [--write]
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import time

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat, _seat_lateral, _settle_modal_coordinates

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s108"
SPEED_M_S = 80.0 / 3.6
ROLL_RADIUS_M = 0.43
SHARE_LO, SHARE_HI = 0.625, 1.6


def seated(case, lateral: bool):
    dynamics = VehicleDynamics(case)
    try:
        v = np.asarray(case.initial_v, dtype=float)
        for index in range(1, 5):
            v[dynamics.topology.require(f"wheelset{index}", "spin")] = SPEED_M_S / ROLL_RADIUS_M
        q = np.asarray(case.initial_q, dtype=float)
        start = time.perf_counter()
        q, residual = _seat(case, dynamics, q, v)
        q = np.asarray(q, dtype=float)
        for _round in range(2):
            q = _settle_modal_coordinates(dynamics, q, v)
            q, residual = _seat(case, dynamics, q, v)
            q = np.asarray(q, dtype=float)
        lateral_residual = float("nan")
        if lateral:
            for _round in range(2):
                q, lateral_residual = _seat_lateral(case, dynamics, q, v)
                q = _settle_modal_coordinates(dynamics, q, v)
                q, residual = _seat(case, dynamics, q, v)
                q = np.asarray(q, dtype=float)
        wall = time.perf_counter() - start
        _, contacts = dynamics.evaluate(0.0, q, v)
        rows = []
        for rail in case.rails:
            response = contacts[rail.id]
            rows.append({
                "rail": rail.id,
                "normal_n": float(response.normal_force_n),
                "lateral_n": float(response.wheel_force_y_n),
                "tilt": float(response.geometry.normal_y) if response.geometry else float("nan"),
                "lever_y_m": float(response.geometry.lever_y_m) if response.geometry else float("nan"),
                "penetration_m": float(response.hertz_penetration_m),
                "wheel_y_m": float(q[dynamics.topology.require(f"wheelset{rail.axle_index + 1}", "y")]),
            })
        return q, float(residual), lateral_residual, wall, rows
    finally:
        dynamics.close()


def summarise(rows):
    total = sum(row["normal_n"] for row in rows)
    share = [row["normal_n"] / (total / len(rows)) for row in rows]
    left = next(row for row in rows if row["rail"].endswith("_left"))
    right = next(row for row in rows if row["rail"].endswith("_right"))
    per_axle = {}
    for row in rows:
        key = row["rail"].split("_")[0]
        per_axle[key] = per_axle.get(key, 0.0) + row["lateral_n"]
    return {
        "total_normal_n": total,
        "share_min": min(share),
        "share_max": max(share),
        "net_lateral_n": sum(row["lateral_n"] for row in rows),
        "per_axle_lateral_n": per_axle,
        "worst_axle_lateral_n": max(abs(value) for value in per_axle.values()),
        "tilt_sum": left["tilt"] + right["tilt"],
        "tilt_left": left["tilt"],
        "tilt_right": right["tilt"],
        "wheel_y_mm": {row["rail"]: row["wheel_y_m"] * 1e3 for row in rows},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    report = {}
    for label, lateral in (("vertical only", False), ("vertical + lateral", True)):
        case = load_vehicle_case(CASE)
        # The canonical case now carries the flag; drive each branch explicitly so the comparison
        # does not depend on what the file happens to say.
        case = dataclasses.replace(case, run=dataclasses.replace(case.run, seat_lateral=lateral))
        q, residual, lateral_residual, wall, rows = seated(case, lateral)
        stats = summarise(rows)
        stats.update({"seat_residual_n": residual, "lateral_seat_residual_n": lateral_residual,
                      "wall_s": wall})
        report[label] = stats
        print(f"--- {label}")
        print(f"    seat residual {residual:.3e} N   lateral residual {lateral_residual:.3e} N"
              f"   wall {wall:.1f} s")
        print(f"    share {stats['share_min']:.3f}..{stats['share_max']:.3f}"
              f"   net lateral {stats['net_lateral_n']:+.2f} N"
              f"   worst axle {stats['worst_axle_lateral_n']:+.2f} N"
              f"   tilt {stats['tilt_left']:+.6f} / {stats['tilt_right']:+.6f}"
              f" (sum {stats['tilt_sum']:+.6f})")
        for rail, value in stats["wheel_y_mm"].items():
            print(f"      {rail:>13} wheel y {value:+8.4f} mm")

    final = report["vertical + lateral"]
    gates = {
        "G1_vertical_seat": final["seat_residual_n"] <= 1e-5
        and SHARE_LO <= final["share_min"] and final["share_max"] <= SHARE_HI,
        "G2_lateral_residual": final["worst_axle_lateral_n"] <= 20.0,
        "G3_tilt_symmetry": abs(final["tilt_sum"]) <= 1.0e-3,
        "G4_seat_cheap": final["wall_s"] <= 60.0,
    }
    for name, passed in gates.items():
        print(f"[{name}] {'PASS' if passed else 'FAIL'}")
    verdict = "PASS" if all(gates.values()) else "FAIL"
    print(f"VERDICT: {verdict}")

    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        payload = {"gates": gates, "verdict": verdict, "states": report,
                   "targets": {"worst_axle_lateral_n": 20.0, "tilt_sum": 1.0e-3,
                               "seat_residual_n": 1e-5, "wall_s": 60.0}}
        (OUT / "lateral_seat.json").write_text(
            json.dumps(payload, indent=1, ensure_ascii=False) + chr(10), encoding="utf-8")
        print(f"report -> {OUT / 'lateral_seat.json'}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
