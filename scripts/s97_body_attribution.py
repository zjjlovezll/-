"""M0：逐体载荷必须加得回车轮合力，而且"降低值 > 静侵入"的尖轨不许承力。

任务书（`docs/TASKBOOK_FINAL_GOAL_2026-10-31.md`）的 M0 有两条硬门，这个脚本一次给出：

1. **加得回去**：每一帧、每一根轨，逐体法向力之和必须等于求解器真正积分的那个合力
   （相对偏差 ≤ 1e-9）。`merge_contact_responses` 按定义求和，所以这条本该恒成立——但
   `_body_cache` 与 `contacts` 是两份产物（前者给雅可比、后者给车轮），一旦有人只改一处，
   两者会悄悄分叉，而这正是"尖轨在 50.627 m 就吃到 69.69 kN"那类读数的来源。
2. **降低值没吃完就不许承力**：尖轨尖端低于走行面 14.94 mm，静侵入只有 65.4661 µm，
   两者差 228 倍。所以尖轨体在 `z_offset` 还没吃完的里程上，法向力必须**恒为 0**；
   第一次承力的帧，它的贯入量必须与静侵入同量级（µm），不是 mm。

为什么要单独做而不是读 `contacts`：`evaluate` 把同一侧多个体合并成一个响应汇报，
合并后的几何取**最深**的那个，于是"这块载荷归谁"在返回值里根本看不见。逐体归属只能
从 `BODY_CONTACT_HOOK` 取，而它在生产路径上是 `None`（本脚本临时挂上，跑完还原）。

用法：
    PYTHONPATH=src python -X utf8 scripts/s97_body_attribution.py --duration 0.55
    PYTHONPATH=src python -X utf8 scripts/s97_body_attribution.py --duration 1.30 --x-start 40
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import time

import numpy as np

import velch.vehicle_solver as vs
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, simulate_vehicle

CASE = pathlib.Path("vehicles/turnouts/CN60-1100-1_18/cases/straight.json")
OUT_ROOT = pathlib.Path("../scratch/s97")
STATIC_PENETRATION_M = 65.4661e-6

#: 尖轨设计的最大降低值与尖轨区起点（`vehicles/turnouts/CN60-1100-1_18/index.json`）。
BLADE_LOWERING_M = 14.94e-3
BLADE_START_M = 50.578
#: Below this mileage the blade is still far below the stock, so any load it reports is attribution,
#: not physics.  The number is *measured* from the drawn sections (scripts/s98_m0_verdict.py): the
#: blade crown crosses the stock crown at 58.423 m and comes within one static penetration at 57.733 m.
#: It is only a coarse alarm here -- s98 owns the criterion, and it derives it from the geometry rather
#: than from this constant, so a rebuilt case cannot silently make this stale.
BLADE_FLAT_SUSPECT_M = 58.423


def run(duration_s: float, x_start_m: float | None, output_step_s: float) -> pathlib.Path:
    case = load_vehicle_case(CASE)
    if x_start_m is not None:
        case = dataclasses.replace(case, run=dataclasses.replace(case.run, x_start_m=float(x_start_m)))
    x_start_effective = float(case.run.x_start_m)
    case = dataclasses.replace(
        case, run=dataclasses.replace(case.run, duration_s=duration_s, output_step_s=output_step_s)
    )

    # Stations come from the same formula the patch evaluation uses: x_at(t) + axle offset.
    probe = VehicleDynamics(case)
    speed = float(case.vehicle.travel_speed_m_s)
    offsets = {rail.id: float(case.vehicle.axle_offsets_m[rail.axle_index]) for rail in case.rails}

    frames: list[dict] = []
    merges: list[dict] = []

    original_merge = vs.merge_contact_responses
    #: spy on the merged response so the identity check compares two independent records
    def merge_spy(responses):
        merged = original_merge(responses)
        merges.append({"total_n": float(merged.normal_force_n) if merged.active else 0.0})
        return merged

    def hook(t_s: float, rail_id: str, entries) -> None:
        frames.append({
            "t": float(t_s),
            "rail": str(rail_id),
            "bodies": [[str(body_id), float(force)] for body_id, force in entries],
        })

    vs.merge_contact_responses = merge_spy
    vs.BODY_CONTACT_HOOK = hook
    started = time.perf_counter()
    try:
        result = simulate_vehicle(case)
    finally:
        vs.merge_contact_responses = original_merge
        vs.BODY_CONTACT_HOOK = None
    wall = time.perf_counter() - started
    probe.close()

    summary = getattr(result, "summary", {}) or {}
    gates = summary.get("gates") or {}

    # ---- criterion 1: sum of bodies == merged, per frame per rail -----------------------------
    if len(merges) != len(frames):
        raise SystemExit(f"merge calls {len(merges)} != hook calls {len(frames)}; pairing is invalid")
    worst, worst_at, compared = 0.0, None, 0
    for merged, frame in zip(merges, frames):
        total = sum(force for _body_id, force in frame["bodies"])
        scale = max(abs(merged["total_n"]), 1.0)
        deviation = abs(total - merged["total_n"]) / scale
        compared += 1
        if deviation > worst:
            worst, worst_at = deviation, frame
    print(f"frames {len(result.times_s)}   pairs compared {compared}")
    print(f"[M0-1] max |sum(bodies) - merged| / merged = {worst:.3e}   (gate 1e-9)")
    if worst_at is not None and worst > 0.0:
        print(f"        worst at t={worst_at['t']:.6f} s rail={worst_at['rail']} "
              f"bodies={[[b, round(f, 3)] for b, f in worst_at['bodies']]}")
    identity_ok = worst <= 1e-9

    # ---- criterion 2: first loaded evaluation per (rail, body) ---------------------------------
    # The hook also fires during the seating iterations, where every wheel is pushed in by the same
    # amount and reports ~2 293 kN (measured: all four axles, identical to 3 dp).  Those are not
    # dynamics, so only t > 0 counts; and a body counts as carrying only above 1 kN, well clear of
    # the numerical floor.
    loaded_gate_n = 1.0e3
    series: dict[tuple[str, str], list[dict]] = {}
    for frame in frames:
        if frame["t"] <= 0.0:
            continue
        station = x_start_effective + speed * frame["t"] + offsets.get(frame["rail"], 0.0)
        for body_id, force in frame["bodies"]:
            series.setdefault((frame["rail"], body_id), []).append(
                {"t": frame["t"], "station_m": station, "force_n": force})

    rows = []
    for (rail_id, body_id), points in sorted(series.items()):
        carrying = [point for point in points if point["force_n"] > loaded_gate_n]
        peak = max(points, key=lambda point: point["force_n"])
        rows.append({
            "rail": rail_id,
            "body": body_id,
            "evaluations": len(points),
            "carrying_evaluations": len(carrying),
            "first_carrying": carrying[0] if carrying else None,
            "peak_n": peak["force_n"],
            "peak_station_m": peak["station_m"],
            "last_n": points[-1]["force_n"],
        })

    print(f"\n[M0-2] per body over t > 0 (carrying = more than {loaded_gate_n / 1e3:.0f} kN):")
    print(f"  {'rail':<13} {'body':<7} {'first (m)':>10} {'N (kN)':>9} "
          f"{'peak N (kN)':>12} {'peak at (m)':>12}")
    for row in rows:
        if "right" not in row["rail"]:
            continue
        first = row["first_carrying"]
        first_station = f"{first['station_m']:10.4f}" if first else f"{'-':>10}"
        first_force = f"{first['force_n'] / 1e3:9.3f}" if first else f"{'-':>9}"
        print(f"  {row['rail']:<13} {row['body']:<7} {first_station} {first_force} "
              f"{row['peak_n'] / 1e3:12.3f} {row['peak_station_m']:12.4f}")

    # A blade that is still metres down cannot be touching a wheel that is 65 um into the stock.
    suspect = [row for row in rows
               if row["body"] == "blade" and row["first_carrying"] is not None
               and row["first_carrying"]["station_m"] < BLADE_FLAT_SUSPECT_M]
    print(f"\n  blade bodies carrying load before {BLADE_FLAT_SUSPECT_M:.1f} m "
          f"(lowering still > 65.4661 um): {len(suspect)}")
    for row in suspect:
        first = row["first_carrying"]
        print(f"    !! {row['rail']} {row['body']} at {first['station_m']:.4f} m "
              f"N {first['force_n'] / 1e3:.3f} kN")

    print("\ngates " + "  ".join(f"{name}={bool(value)}" for name, value in gates.items()))
    print(f"wall {wall:.0f} s for {duration_s:.3f} s simulated")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    out = OUT_ROOT / f"attribution_{duration_s:.2f}s.json"
    out.write_text(json.dumps({
        "case": str(CASE),
        "duration_s": duration_s,
        "x_start_m": x_start_effective,
        "speed_m_s": speed,
        "static_penetration_m": STATIC_PENETRATION_M,
        "identity_max_relative": worst,
        "identity_gate": 1e-9,
        "identity_ok": identity_ok,
        "first_loaded": rows,
        "blade_loaded_before_flat": suspect,
        "gates": gates,
        "wall_s": wall,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", out)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=0.55)
    parser.add_argument("--x-start", type=float, default=None)
    parser.add_argument("--output-step", type=float, default=5e-4)
    args = parser.parse_args()

    run(args.duration, args.x_start, args.output_step)
