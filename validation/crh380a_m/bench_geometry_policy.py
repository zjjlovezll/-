"""Benchmark the contact-geometry policies on one real state set.

Measures the cost of one contact evaluation and the agreement of the refined
(fixed uniform grid + parabolic extremum) evaluation against the historical
merged grid, on the same wheel/rail poses.

Usage::

    python bench_geometry_policy.py <case.json> [--from 79.0] [--to 84.0] [--n 201]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from velch.contact import find_graph_contact          # noqa: E402
from velch.vehicle import load_vehicle_case           # noqa: E402


def _wheel_of(case, rail):
    for wheel in case.wheels:
        if wheel.id == rail.wheel_id:
            return wheel
    raise SystemExit(f"no wheel {rail.wheel_id}")


def _poses(case, rail_id, x_from, x_to, count):
    rail = next(r for r in case.rails if r.id == rail_id)
    wheel = _wheel_of(case, rail)
    bodies = rail.contact_bodies
    q = np.asarray(case.initial_q, float)
    wh = 5 * rail.axle_index
    poses = []
    for x in np.linspace(x_from, x_to, count):
        body = next((b for b in bodies if b.active_at(float(x))), None)
        if body is None:
            body = next((b for b in bodies if b.series.covers(float(x))), None)
        if body is None:
            continue
        poses.append({
            "sample": body.series.sample(float(x), 1),
            "wheel_y_m": float(q[wh]),
            "wheel_z_m": case.vehicle.wheel_center_height_m + float(q[wh + 1]),
            "wheel_roll_rad": float(q[wh + 2]),
            "wheel_lateral_offset_m": wheel.lateral_offset_m,
            "x": float(x),
        })
    return wheel, rail, poses


def _evaluate(wheel, pose, *, geometry_policy, grid_step_m=0.0):
    return find_graph_contact(
        wheel.profile, pose["sample"],
        wheel_y_m=pose["wheel_y_m"], wheel_z_m=pose["wheel_z_m"],
        wheel_roll_rad=pose["wheel_roll_rad"],
        wheel_lateral_offset_m=pose["wheel_lateral_offset_m"],
        rail_y_m=0.753, rail_z_m=0.0,
        geometry_policy=geometry_policy, grid_step_m=grid_step_m,
    )


def _time_policy(wheel, poses, *, geometry_policy, grid_step_m=0.0, repeats=3):
    best = float("inf")
    result = []
    for _ in range(repeats):
        start = time.perf_counter()
        result = [_evaluate(wheel, pose, geometry_policy=geometry_policy,
                            grid_step_m=grid_step_m) for pose in poses]
        best = min(best, time.perf_counter() - start)
    return best / len(poses) * 1e6, result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("--rail", default="axle1_right")
    parser.add_argument("--from", dest="x_from", type=float, default=79.0)
    parser.add_argument("--to", dest="x_to", type=float, default=84.0)
    parser.add_argument("--n", type=int, default=201)
    parser.add_argument("--variants", default="0,1e-4,5e-5")
    args = parser.parse_args()

    case = load_vehicle_case(args.case)
    wheel, rail, poses = _poses(case, args.rail, args.x_from, args.x_to, args.n)
    print(f"case      : {case.case_id}")
    print(f"rail      : {rail.id}  bodies={[b.id for b in rail.contact_bodies]}")
    print(f"poses     : {len(poses)}  x={args.x_from:g}..{args.x_to:g} m")
    print()

    reference_us, reference = _time_policy(wheel, poses, geometry_policy="grid")
    loaded = [i for i, g in enumerate(reference) if g is not None and g.penetration_m > 0.0]
    print(f"{'policy':<12}{'step mm':>9}{'us/call':>10}{'speedup':>9}"
          f"{'max|dy| um':>12}{'max|dpen| um':>14}{'max|dR*| %':>12}")
    print(f"{'grid':<12}{'-':>9}{reference_us:>10.2f}{1.0:>9.2f}{'-':>12}{'-':>14}{'-':>12}")

    rows = []
    for text in args.variants.split(","):
        step = float(text)
        us, values = _time_policy(wheel, poses, geometry_policy="fixed_grid",
                                  grid_step_m=step)
        dy = dp = dr = 0.0
        compared = 0
        for i in loaded:
            ref, got = reference[i], values[i]
            if ref is None or got is None:
                continue
            dy = max(dy, abs(got.y_m - ref.y_m) * 1e6)
            dp = max(dp, abs(got.penetration_m - ref.penetration_m) * 1e6)
            if ref.radius_star_m > 0:
                dr = max(dr, abs(got.radius_star_m - ref.radius_star_m)
                         / ref.radius_star_m * 100.0)
            compared += 1
        rows.append({"grid_step_m": step, "us_per_call": us,
                     "speedup": reference_us / us, "max_dy_um": dy,
                     "max_dpen_um": dp, "max_dr_percent": dr, "compared": compared})
        print(f"{'fixed_grid':<12}{step * 1e3:>9.3f}{us:>10.2f}"
              f"{reference_us / us:>9.2f}{dy:>12.3f}{dp:>14.4f}{dr:>12.2f}")

    print()
    print(f"loaded stations compared: {len(loaded)}")
    out = Path(args.case).with_name("bench_geometry_policy.json")
    out.write_text(json.dumps({"case": case.case_id, "rail": rail.id,
                               "poses": len(poses), "loaded": len(loaded),
                               "reference_us_per_call": reference_us,
                               "variants": rows,
                               "median_reference_penetration_um":
                                   statistics.median([reference[i].penetration_m * 1e6
                                                      for i in loaded])},
                              indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
