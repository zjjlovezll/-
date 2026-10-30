"""Run the fixed 18-turnout baseline and keep the data.

The straight route is the one the database can already describe: one stock section per station, a
blade body from 50.578 m and a point-rail body from 103.28 m, crowns 13.0 mm outboard of the wheel
centre (measured: the seat converges with eight wheels at 1.000x for every offset in 12.0-13.7 mm and
loses contact outside 10-14 mm).

The diverging route is NOT described by this database yet: its lateral geometry lives in the
per-mileage profile files (and in the qjg_cgyg table), not in the single stock section the straight
baseline repeats, so building it here would invent a route.  That is the next job, and this script
refuses to fake it.

Usage:
    PYTHONPATH=src python -X utf8 scripts/s86_run_baseline.py --route straight --duration 0.20
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

CASE = pathlib.Path("vehicles/turnouts/CN60-1100-1_18/cases/straight.json")
OUT_ROOT = pathlib.Path("../scratch/s86")


def run(route: str, duration_s: float, output_step_s: float) -> pathlib.Path:
    if route != "straight":
        raise SystemExit(
            "the database has no diverging geometry yet: the route lateral comes from the per-mileage "
            "profile files, not from the single stock section this case repeats. Build that line first."
        )
    case = load_vehicle_case(CASE)
    case = dataclasses.replace(
        case, run=dataclasses.replace(case.run, duration_s=duration_s, output_step_s=output_step_s)
    )
    result = simulate_vehicle(case)
    summary = getattr(result, "summary", {}) or {}
    out = OUT_ROOT / f"{route}_{duration_s:.2f}s"
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out / "series.npz",
        times=np.asarray(result.times_s),
        positions=np.asarray(result.positions),
        velocities=np.asarray(result.velocities),
    )
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    gates = summary.get("gates") or {}
    print(f"{route}: frames {len(result.times_s)}  gates {sum(bool(v) for v in gates.values())}/{len(gates)}")
    for name, value in gates.items():
        print(f"  {name}: {value}")
    print(f"data -> {out}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", default="straight", choices=("straight", "diverging"))
    parser.add_argument("--duration", type=float, default=0.20)
    parser.add_argument("--output-step", type=float, default=5e-4)
    args = parser.parse_args()
    run(args.route, args.duration, args.output_step)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
