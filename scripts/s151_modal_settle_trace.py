"""Trace the modal settle: how far the tread is pushed, per round, at 60 and 80 km/h.

Round 294 localised the corrected 60 km/h stall to the seat that follows the first modal settle.
This probe opens that settle (``_settle_modal_coordinates`` is a fixed-point iteration
``q_modal += K^-1 force[modal]`` with a contraction near 0.755 per pass) and records, per round,
the largest step and the largest modal coordinate.

The point is to see whether 60 km/h converges to a *different* tread state than 80 km/h, or whether
it fails to converge at all -- two different repairs.  It reports steps and coordinates only: no
amplitude, no speed-transfer claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import velch.vehicle_solver as vs  # noqa: E402
from velch.solver import SimulationFailure  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402

CASE = Path(r"F:/ai道岔状态反演辨识/scratch/s146/one_set_x46.json")
SPEEDS = (60.0, 80.0)
ROUNDS = 20
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "modal_settle_trace.json"


def trace(case, speed_kmh, rounds=ROUNDS):
    dyn = vs.VehicleDynamics(case)
    q = np.asarray(case.initial_q, dtype=float)
    v = np.asarray(case.initial_v, dtype=float)
    for axle in (1, 2, 3, 4):
        v[dyn.topology.require(f"wheelset{axle}", "spin")] = speed_kmh / 3.6 / 0.43
    q, residual = vs._seat(case, dyn, q, v)
    modal = dyn.modal
    if modal is None:
        return {"speed_kmh": speed_kmh, "modal": False}
    stiffness = modal.stiffness()
    settled = np.array(q, dtype=float)
    steps, blocks = [], []
    for index in range(rounds):
        force, _contacts = dyn.evaluate(0.0, settled, v)
        step = np.linalg.solve(stiffness, force[modal.offset:])
        settled[modal.offset:] += step
        steps.append(float(np.max(np.abs(step))))
        blocks.append(float(np.max(np.abs(settled[modal.offset:]))))
        if steps[-1] < 1e-9:
            break
    seat_after = {"ok": None}
    try:
        out, residual2 = vs._seat(case, dyn, settled, v)
        seat_after = {
            "ok": True,
            "residual_n": float(residual2),
            "wheel_z_um": float(out[dyn.topology.require("wheelset1", "z")]) * 1e6,
            "wheel_y_um": float(out[dyn.topology.require("wheelset1", "y")]) * 1e6,
        }
    except SimulationFailure as exc:
        seat_after = {"ok": False, "error": str(exc).splitlines()[0][:140]}
    return {
        "speed_kmh": speed_kmh,
        "modal": True,
        "seat1_residual_n": float(residual),
        "rounds": len(steps),
        "steps_m": steps,
        "block_max_m": blocks,
        "ratio": [steps[i + 1] / steps[i] for i in range(len(steps) - 1) if steps[i] > 0],
        "seat_after": seat_after,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speeds", nargs="+", type=float, default=list(SPEEDS))
    parser.add_argument("--rounds", type=int, default=ROUNDS)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    case = load_vehicle_case(CASE)
    records = []
    for speed in args.speeds:
        record = trace(case, speed, args.rounds)
        records.append(record)
        if not record.get("modal"):
            print(f"== {speed:.0f} km/h: no modal block")
            continue
        steps = record["steps_m"]
        print(f"== {speed:.0f} km/h   seat#1 {record['seat1_residual_n']:.2e} N   rounds {record['rounds']}")
        for index in range(0, len(steps), 4):
            print(f"   round {index + 1:2d}  |step| {steps[index]:.3e} m  "
                  f"|modal| {record['block_max_m'][index]:.3e} m  "
                  f"ratio {record['ratio'][index - 1] if 0 < index <= len(record['ratio']) else float('nan'):.3f}")
        if steps:
            print(f"   last |step| {steps[-1]:.3e} m   median ratio "
                  f"{float(np.median(record['ratio'])):.3f}" if record["ratio"] else "")
        after = record["seat_after"]
        print("   seat#2 -> " + (f"ok, {after['residual_n']:.2e} N, z {after['wheel_z_um']:.1f} um, "
                                 f"y {after['wheel_y_um']:+.1f} um" if after["ok"] else f"FAILED: {after['error'][:70]}"))

    converged = {r["speed_kmh"]: (r.get("steps_m") or [1.0])[-1] < 1e-9 for r in records if r.get("modal")}
    print()
    print(f"[SETTLE] converged within {args.rounds} rounds: {converged}")
    print("[SETTLE] a smaller final step with a failing seat means the seat, not the settle, is short")
    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps({"case": str(CASE), "records": records}, indent=2), encoding="utf-8")
        print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
