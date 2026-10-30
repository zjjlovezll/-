"""Check the M1 "one set" run: does the complete car, flexible wheelsets, compliant track and the
real turnout geometry survive the trip across the switch blade?

The pre-registered M1 gates (``docs/TASKBOOK_FINAL_GOAL_2026-10-31.md``) are:

    G1  the case loads with 234 coordinates = 86 vehicle + 16 track + 132 modal, 15 bodies
    G2  the seat finds 8/8 contacts in [0.625, 1.6] x fair share
    G3  the integration reports ``numerically_checked`` with all seven gates
    G4  the front axle crosses the blade tip (50.578 m) and the first-load station (58.1 m)
    G5  load share stays inside [0.625, 1.6] x for every rail over the whole run

G4 is read from the archived series, never from a separate summary: the station of axle ``k`` is
``x_start + v t + offsets[k]`` (``vehicle.py:104``) and the blade force comes from the per-body
column block, because the merged rail force cannot say which body carries the wheel.

    PYTHONPATH=src python -X utf8 scripts/s102_one_set_check.py
    PYTHONPATH=src python -X utf8 scripts/s102_one_set_check.py --run-id <id> --write
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

from velch.vehicle import load_vehicle_case

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNS = ROOT.parent / "scratch" / "runs"
OUT = ROOT.parent / "scratch" / "s102"
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"

BLADE_TIP_M = 50.578
BLADE_FIRST_TOUCH_M = 57.733          # geometric, from s98
BLADE_FLUSH_M = 58.423
SHARE_LO = 0.625
SHARE_HI = 1.6
BLADE_LOAD_N = 1.0e3                  # a body counts as loaded once it carries a kilonewton


def latest_run(campaign: str) -> pathlib.Path:
    index = RUNS / "index.jsonl"
    if not index.exists():
        raise SystemExit(f"no archive index at {index}")
    rows = [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines() if line.strip()]
    chosen = []
    for row in rows:
        meta_path = pathlib.Path(row["path"]) / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if (meta.get("notes") or {}).get("campaign") == campaign:
            chosen.append((float(meta["speed_kmh"]), float(meta["duration_s"]), row["run_id"]))
    if not chosen:
        raise SystemExit(f"no archived run carries notes.campaign={campaign!r}")
    speed, duration, run_id = sorted(chosen)[-1]
    return RUNS / run_id


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--campaign", default="one-set-m1")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    run_dir = RUNS / args.run_id if args.run_id else latest_run(args.campaign)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    series = np.load(run_dir / "series.npz")

    case = load_vehicle_case(CASE)
    offsets = list(case.vehicle.axle_offsets_m)
    speed = float(meta["speed_m_s"])
    x_start = float(meta["x_start_m"])
    times = np.asarray(series["times"], dtype=float)
    stations_of_front = x_start + speed * times + offsets[0]

    normal = np.asarray(series["normal_force_n"], dtype=float)
    body_normal = np.asarray(series["body_normal_force_n"], dtype=float)
    rail_ids = list(meta["rail_ids"])
    body_labels = list(meta["body_labels"])

    # G3: the seven gates the solver itself reports.
    gates = {str(k): bool(v) for k, v in (meta.get("gates") or {}).items()}
    gates_ok = bool(gates) and all(gates.values())

    # G5: share of the instantaneous total.  Normalising by the running total (not by the seated
    # weight) keeps the statement true even while the car is still settling.
    total = normal.sum(axis=1)
    share = np.where(total[:, None] > 0.0, normal * len(rail_ids) / np.maximum(total, 1e-9)[:, None], 0.0)
    share_min = float(share.min())
    share_max = float(share.max())
    worst_row, worst_col = np.unravel_index(np.argmax(np.abs(share - 1.0)), share.shape)
    share_ok = bool(SHARE_LO <= share_min and share_max <= SHARE_HI)

    # G4a: did the front axle actually reach the blade tip?
    reached_tip = float(stations_of_front.max())

    # G4b: when does the blade first carry load?  Read the per-body columns for the front axle.
    lower = stations_of_front >= BLADE_TIP_M
    blade_columns = [i for i, label in enumerate(body_labels)
                     if label.startswith("axle1_right/") and label.endswith("/blade")]
    stock_columns = [i for i, label in enumerate(body_labels)
                     if label.startswith("axle1_right/") and label.endswith("/stock")]
    blade_series = body_normal[:, blade_columns].sum(axis=1) if blade_columns else np.zeros_like(times)
    stock_series = body_normal[:, stock_columns].sum(axis=1) if stock_columns else np.zeros_like(times)
    loaded = np.nonzero(blade_series >= BLADE_LOAD_N)[0]
    first_load_station = float(stations_of_front[loaded[0]]) if loaded.size else None
    peak_index = int(np.argmax(blade_series)) if blade_series.size else 0
    peak_station = float(stations_of_front[peak_index])
    peak_force = float(blade_series[peak_index])
    stock_at_peak = float(stock_series[peak_index])

    crossing_ok = bool(loaded.size) and first_load_station is not None and first_load_station >= BLADE_TIP_M
    cross_tip_ok = reached_tip >= BLADE_TIP_M
    cross_first_touch_ok = reached_tip >= BLADE_FIRST_TOUCH_M

    report = {
        "run_id": run_dir.name,
        "campaign": (meta.get("notes") or {}).get("campaign"),
        "case": meta.get("case"),
        "dimension": int(meta["dimension"]),
        "speed_kmh": float(meta["speed_kmh"]),
        "duration_s": float(meta["duration_s"]),
        "frames": int(times.size),
        "wall_s": float(meta.get("wall_s", float("nan"))),
        "body_labels": body_labels,
        "rail_ids": rail_ids,
        "gates": gates,
        "m1_g3_seven_gates_ok": gates_ok,
        "share_min": share_min,
        "share_max": share_max,
        "share_worst_rail": rail_ids[int(worst_col)],
        "share_worst_station_m": float(stations_of_front[worst_row]),
        "m1_g5_share_ok": share_ok,
        "front_axle_reached_m": reached_tip,
        "m1_g4_crossed_blade_tip": cross_tip_ok,
        "m1_g4_crossed_first_touch": cross_first_touch_ok,
        "blade_first_load_m": first_load_station,
        "blade_first_load_offset_vs_geometry_m": (
            None if first_load_station is None else first_load_station - BLADE_FIRST_TOUCH_M),
        "m1_g4b_blade_loads_after_tip": crossing_ok,
        "blade_peak_force_n": peak_force,
        "blade_peak_station_m": peak_station,
        "stock_force_at_blade_peak_n": stock_at_peak,
        "blade_share_of_right_side_at_peak": (
            float(peak_force / (peak_force + stock_at_peak)) if peak_force + stock_at_peak > 0 else None),
        "frames_with_blade_load": int(loaded.size),
        "lower_bracket_samples": int(lower.sum()),
    }

    print(f"run {report['run_id']}  dimension {report['dimension']}  "
          f"{report['frames']} frames  {report['speed_kmh']:.2f} km/h  wall {report['wall_s']:.1f} s")
    print(f"[G3] seven gates {sum(gates.values())}/{len(gates)} -> {'PASS' if gates_ok else 'FAIL'}")
    print(f"[G5] share {share_min:.3f} .. {share_max:.3f} (worst {report['share_worst_rail']} at "
          f"{report['share_worst_station_m']:.3f} m) -> {'PASS' if share_ok else 'FAIL'}")
    print(f"[G4] front axle reached {reached_tip:.3f} m  (tip {BLADE_TIP_M:.3f}, "
          f"first touch {BLADE_FIRST_TOUCH_M:.3f})")
    if first_load_station is None:
        print("[G4b] the blade never carries load -> FAIL")
    else:
        print(f"[G4b] blade first load at {first_load_station:.3f} m "
              f"({report['blade_first_load_offset_vs_geometry_m']:+.3f} m vs geometry), "
              f"peak {peak_force / 1e3:.2f} kN at {peak_station:.3f} m "
              f"(stock there {stock_at_peak / 1e3:.2f} kN)")
    print(f"body columns: {len(body_labels)}  (blade {len(blade_columns)}, stock {len(stock_columns)})")

    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "one_set_check.json").write_text(
            json.dumps(report, indent=1, ensure_ascii=False) + chr(10), encoding="utf-8")
        print(f"report -> {OUT / 'one_set_check.json'}")
    ok = gates_ok and share_ok and cross_tip_ok and crossing_ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
