"""Attribute find_graph_contact's per-call cost to its individual stages.

Runs the real CRH380A_M wheel/rail graph pair through each stage of the
routine separately, so the optimisation target is measured rather than guessed.
"""

from __future__ import annotations

import math
import statistics
import time
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case

CASE = Path("validation/crh380a_m/case_B_turnout.json")
REPEATS = 2000
WHEEL_Z_M = 0.43 - 0.000463


def bench(fn, repeats: int = REPEATS) -> float:
    samples = []
    for _ in range(5):
        t0 = time.perf_counter()
        for _ in range(repeats):
            fn()
        samples.append((time.perf_counter() - t0) / repeats)
    return statistics.median(samples)


def main() -> None:
    case = load_vehicle_case(CASE)
    rail = case.rails[0]
    wheel = {item.id: item for item in case.wheels}[rail.wheel_id]
    sample = rail.profiles.sample(23.5, 1)

    profile_y = wheel.profile.y_m
    profile_z = wheel.profile.z_m
    offset = wheel.lateral_offset_m
    rail_y_ref = sample.profile.y_m
    rail_z_ref = sample.profile.z_m
    rail_dz_ds = sample.dz_ds

    state = {}

    def stage_transform() -> None:
        local_y = offset + profile_y
        c, s = math.cos(0.0), math.sin(0.0)
        wy = 0.0 + c * local_y - s * profile_z
        wz = WHEEL_Z_M + s * local_y + c * profile_z
        state["wy"], state["wz"] = wy, wz

    def stage_monotonic() -> None:
        np.all(np.diff(state["wy"]) > 0)

    def stage_merge() -> None:
        ry = 0.0 + rail_y_ref
        rz = 0.0 + rail_z_ref
        lower, upper = max(state["wy"][0], ry[0]), min(state["wy"][-1], ry[-1])
        grid = np.unique(np.concatenate((
            np.array([lower, upper]),
            state["wy"][(state["wy"] > lower) & (state["wy"] < upper)],
            ry[(ry > lower) & (ry < upper)],
        )))
        state["grid"] = grid
        state["ry"], state["rz"] = ry, rz

    def stage_interp() -> None:
        state["w_z"] = np.interp(state["grid"], state["wy"], state["wz"])
        state["r_z"] = np.interp(state["grid"], state["ry"], state["rz"])

    def stage_slopes() -> None:
        slopes = np.gradient(state["r_z"], state["grid"], edge_order=1)
        inv = 1.0 / np.sqrt(1.0 + slopes * slopes)
        state["slopes"] = slopes
        state["inv"] = inv

    def stage_depth() -> None:
        signed = (state["r_z"] - state["w_z"]) * state["inv"]
        state["index"] = int(np.argmax(signed))
        state["depth"] = float(signed[state["index"]])

    def stage_dzds() -> None:
        np.interp(float(state["grid"][state["index"]]), rail_y_ref, rail_dz_ds)

    stage_transform()
    stage_merge()
    stage_interp()
    stage_slopes()
    stage_depth()
    stage_dzds()

    print(f"grid points after merge : {state['grid'].size} "
          f"(wheel {profile_y.size}, rail {rail_y_ref.size})")
    print(f"contact at y            : {state['grid'][state['index']] * 1e3:.3f} mm  "
          f"depth {state['depth'] * 1e3:.4f} mm")
    print()
    total = 0.0
    for name, fn in (
        ("transform (282 pts)", stage_transform),
        ("monotonic check", stage_monotonic),
        ("concat+unique merge", stage_merge),
        ("2x np.interp on grid", stage_interp),
        ("np.gradient+sqrt", stage_slopes),
        ("depth+argmax", stage_depth),
        ("dz_ds interp", stage_dzds),
    ):
        cost = bench(fn)
        total += cost
        print(f"{name:24s}: {cost * 1e6:7.1f} us")
    print(f"{'sum of stages':24s}: {total * 1e6:7.1f} us")

    def stage_merge_only() -> None:
        ry = state["ry"]
        rz = state["rz"]
        lower, upper = max(state["wy"][0], ry[0]), min(state["wy"][-1], ry[-1])
        np.unique(np.concatenate((
            np.array([lower, upper]),
            state["wy"][(state["wy"] > lower) & (state["wy"] < upper)],
            ry[(ry > lower) & (ry < upper)],
        )))

    def window_search() -> None:
        """Warm-started local search: only keep points near the last contact."""
        centre = state["grid"][state["index"]]
        span = 2.0e-3
        wy, wz = state["wy"], state["wz"]
        ry, rz = state["ry"], state["rz"]
        w_mask = (wy > centre - span) & (wy < centre + span)
        r_mask = (ry > centre - span) & (ry < centre + span)
        grid = np.unique(np.concatenate((wy[w_mask], ry[r_mask])))
        w_z = np.interp(grid, wy, wz)
        r_z = np.interp(grid, ry, rz)
        slopes = np.gradient(r_z, grid, edge_order=1)
        inv = 1.0 / np.sqrt(1.0 + slopes * slopes)
        signed = (r_z - w_z) * inv
        int(np.argmax(signed))

    print()
    print(f"{'concat+unique alone':24s}: {bench(stage_merge_only) * 1e6:7.1f} us")
    print(f"{'local window (+/-2 mm)':24s}: {bench(window_search) * 1e6:7.1f} us")


if __name__ == "__main__":
    main()
