"""M4: how much of the rail head the run actually measured -- the observed region Omega_obs.

The final goal says "invert the whole 3-D surface of the blade/frog".  A single pass of one vehicle
cannot see the whole head: the wheel runs along one lateral offset (0.4 mm of drift over 0.40 s), so
what any inversion can claim is a *band* around that offset.  This script turns that sentence into a
number, because the number decides what may be called "a surface" and what may not.

Definition, fixed before the numbers are read:

    cell          (station bin 0.20 m) x (lateral bin 1 mm, relative to that station's stock crown)
    patch         the contact band of one rail in one frame: [y - b, y + b] at station s
    Omega_obs     the cells covered by at least one patch, per rail and per station bin
    Omega_design  the cells of the running surface: points within HEAD_DEPTH of the crown of that
                  rail at that station, **restricted to the station bins the run actually visited**
                  (a station the vehicle never reached is not a lateral miss, and counting it would
                  make the number depend on how long the run was)
    coverage      sum over rails |Omega_obs and Omega_design| / sum over rails |Omega_design|

The primary denominator is 5 mm (pre-registered: the part of the head a wheel could plausibly touch
within one contact patch).  The 1/2/10 mm readings are reported beside it because the verdict is
sensitive to that choice, and hiding it would be a way of changing the threshold after the fact.

Pre-registered reading (written here, not after seeing the result):

    coverage >= 0.90                      the run saw the head          -> "surface"
    0.50 <= coverage < 0.90               it saw a band of it           -> "contact-band surface"
    coverage < 0.50                       it saw a narrow strip         -> "contact band only"

Anything below 0.90 forbids the word "surface" in a result, and the gap must be reported next to the
claimed accuracy (`docs/TASKBOOK_FINAL_GOAL_2026-10-31.md` M4).

    PYTHONPATH=src python -X utf8 scripts/s111_obs_region.py [--run-id ...] [--write]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

import numpy as np

from velch.vehicle import load_vehicle_case

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNS = ROOT.parent / "scratch" / "runs"
OUT = ROOT.parent / "scratch" / "s111"
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
S_BIN_M = 0.20
Y_BIN_M = 1.0e-3
HEAD_DEPTHS_M = (1.0e-3, 2.0e-3, 5.0e-3, 10.0e-3)
PRIMARY_DEPTH_M = 5.0e-3
AXLE = re.compile(r"axle(\d+)_")


def latest_one_set_run(minimum_duration_s: float = 0.40) -> str:
    rows = [json.loads(line) for line in (RUNS / "index.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    candidates = [row for row in rows
                  if row["route"] == "straight_one_set" and row["duration_s"] >= minimum_duration_s]
    if not candidates:
        raise SystemExit("no archived one-set run of at least 0.40 s; run scripts/s99_run_archive.py")
    return str(candidates[-1]["run_id"])


def head_profiles(case):
    """Per rail id: (crown, [(station, y, z)] of its running surface, sampled every S_BIN_M)."""

    out = {}
    for rail in case.rails:
        body = next((item for item in rail.contact_bodies if item.id in ("stock", "main")),
                    rail.contact_bodies[0])
        low, high = float(body.series.lowest_m), float(body.series.highest_m)
        stations = np.arange(low, min(high, low + 120.0), S_BIN_M)
        samples, crowns = [], []
        for station in stations:
            sample = body.series.sample(float(station), 1.0)
            y = np.asarray(sample.profile.y_m, dtype=float)
            z = np.asarray(sample.profile.z_m, dtype=float)
            if y.size < 2:
                continue
            samples.append((float(station), y, z))
            crowns.append(float(np.max(z)))
        out[rail.id] = {"crown": float(np.median(crowns)), "samples": samples}
    return out


def design_cells(profile: dict, depth_m: float, bin_lo: int, bin_hi: int) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    crown = profile["crown"]
    for station, y, z in profile["samples"]:
        bin_s = int(np.floor(station / S_BIN_M))
        if bin_s < bin_lo or bin_s > bin_hi:
            continue
        top = z >= (float(np.max(z)) - depth_m)
        if top.sum() < 2:
            continue
        for bin_y in range(int(np.floor((float(y[top].min()) - crown) / Y_BIN_M)),
                           int(np.floor((float(y[top].max()) - crown) / Y_BIN_M)) + 1):
            cells.add((bin_s, bin_y))
    return cells


def head_width_mm(profile: dict, depth_m: float) -> float:
    widths = []
    for _, y, z in profile["samples"]:
        top = z >= (float(np.max(z)) - depth_m)
        if top.sum() >= 2:
            widths.append((float(y[top].max()) - float(y[top].min())) * 1e3)
    return float(np.median(widths)) if widths else float("nan")


def observed_cells(data, meta, profiles, offsets):
    """Per rail: the cells a patch touched, and the station bins the run reached."""

    times = np.asarray(data["times"], dtype=float)
    contact_y = np.asarray(data["contact_lateral_m"], dtype=float)
    contact_b = np.asarray(data["contact_half_width_m"], dtype=float)
    rail_ids = list(meta["rail_ids"])
    speed = float(meta["speed_kmh"]) / 3.6
    x_start = float(meta["x_start_m"])
    touched: dict[str, set[tuple[int, int]]] = {rail_id: set() for rail_id in rail_ids}
    visited: dict[str, tuple[int, int]] = {}
    for column, rail_id in enumerate(rail_ids):
        axle = int(AXLE.search(rail_id).group(1)) - 1
        crown = profiles[rail_id]["crown"]
        stations = x_start + speed * times + offsets[axle]
        visited[rail_id] = (int(np.floor(stations.min() / S_BIN_M)),
                            int(np.floor(stations.max() / S_BIN_M)))
        for row in range(times.size):
            if not (np.isfinite(contact_y[row, column]) and np.isfinite(contact_b[row, column])):
                continue
            lo = contact_y[row, column] - contact_b[row, column] - crown
            hi = contact_y[row, column] + contact_b[row, column] - crown
            bin_s = int(np.floor(stations[row] / S_BIN_M))
            for bin_y in range(int(np.floor(lo / Y_BIN_M)), int(np.floor(hi / Y_BIN_M)) + 1):
                touched[rail_id].add((bin_s, bin_y))
    return touched, visited


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    run_id = args.run_id or latest_one_set_run()
    run_dir = RUNS / run_id
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    data = np.load(run_dir / "series.npz")

    case = load_vehicle_case(CASE)
    offsets = np.asarray(case.vehicle.axle_offsets_m, dtype=float)
    profiles = head_profiles(case)
    touched, visited = observed_cells(data, meta, profiles, offsets)

    band = []
    for rail_id, cells in touched.items():
        per_station: dict[int, set[int]] = {}
        for bin_s, bin_y in cells:
            per_station.setdefault(bin_s, set()).add(bin_y)
        band.extend(len(bins) * Y_BIN_M * 1e3 for bins in per_station.values())
    band = np.array(band)

    readings = []
    for depth in HEAD_DEPTHS_M:
        design_total = inside_total = 0
        per_rail = {}
        for rail_id, cells in touched.items():
            lo, hi = visited[rail_id]
            design = design_cells(profiles[rail_id], depth, lo, hi)
            inside = cells & design
            design_total += len(design)
            inside_total += len(inside)
            per_rail[rail_id] = (len(inside) / len(design)) if design else float("nan")
        readings.append({
            "depth_m": depth,
            "head_width_mm": head_width_mm(profiles["axle1_right"], depth),
            "design_cells": design_total,
            "inside": inside_total,
            "coverage": inside_total / design_total if design_total else float("nan"),
            "per_rail_min": float(np.nanmin(list(per_rail.values()))),
            "per_rail_max": float(np.nanmax(list(per_rail.values()))),
            "primary": abs(depth - PRIMARY_DEPTH_M) < 1e-12,
        })

    primary = next(item for item in readings if item["primary"])
    if primary["coverage"] >= 0.90:
        verdict = "surface"
    elif primary["coverage"] >= 0.50:
        verdict = "contact-band surface"
    else:
        verdict = "contact band only"

    print(f"run {run_id}")
    print(f"  frames {data['times'].size}  rails {len(meta['rail_ids'])}  "
          f"speed {meta['speed_kmh']:.2f} km/h")
    span = [min(item[0] for item in visited.values()) * S_BIN_M,
            (max(item[1] for item in visited.values()) + 1) * S_BIN_M]
    print(f"  visited stations {span[0]:.1f} .. {span[1]:.1f} m")
    print(f"  band covered per rail per station {band.min():.1f} .. {band.max():.1f} mm "
          f"(median {np.median(band):.1f})")
    print()
    print("  depth   head width   Omega_design   covered   coverage   per rail")
    for item in readings:
        mark = "*" if item["primary"] else " "
        print(f" {mark}{item['depth_m']*1e3:5.0f} mm  {item['head_width_mm']:8.2f} mm  "
              f"{item['design_cells']:11d}  {item['inside']:8d}  {item['coverage']*100:6.1f} %   "
              f"{item['per_rail_min']*100:5.1f}..{item['per_rail_max']*100:5.1f} %")
    print(f"\n  primary denominator {PRIMARY_DEPTH_M*1e3:.0f} mm -> coverage "
          f"{primary['coverage']*100:.1f} %  ->  {verdict}")

    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": run_id,
            "verdict": verdict,
            "primary_depth_m": PRIMARY_DEPTH_M,
            "primary_coverage": float(primary["coverage"]),
            "readings": readings,
            "band_width_mm": {"min": float(band.min()), "max": float(band.max()),
                              "median": float(np.median(band))},
            "visited_bins": {rail_id: [int(lo), int(hi)] for rail_id, (lo, hi) in visited.items()},
            "bins": {"station_m": S_BIN_M, "lateral_m": Y_BIN_M},
        }
        (OUT / "obs_region.json").write_text(
            json.dumps(payload, indent=1, ensure_ascii=False) + chr(10), encoding="utf-8")
        print(f"report -> {OUT / 'obs_region.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
