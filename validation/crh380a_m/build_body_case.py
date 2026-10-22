"""Build a multi-body right-rail case for the 18# turnout frog.

The 236 stored cross-sections of the right rail are merged single polylines.
Inside the frog the wing rail and the point rail are two physically separate
bodies that the merge destroys: the contact search then jumps 38 mm sideways in
one station step (x = 79.952 -> 79.982 m) and the shock is amplified into the
599 kN spike.

This script re-splits every cross-section in the region where the two bodies are
genuinely separate (79.131 - 84.324 m), follows the point rail by lateral
continuity from its thin nose, and emits two bodies per side:

  main  : the merged section with the point-rail component removed
  point : the point-rail component alone, active only in its own mileage range

Outside that range the right rail keeps its original single merged body, and the
left rail (a plain rail on this side of a right-hand turnout) is untouched.

Usage:
    python build_body_case.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from prep_bodies import envelope, load_section, segment

BASE = Path(__file__).resolve().parent
CASE_IN = BASE / "case_B_turnout.json"
CASE_OUT = BASE / "case_C_bodies.json"
BODY_DIR = BASE / "bodies"

S_FIRST = 79.131
MATCH_DY = 0.008   # 8 mm lateral continuity between neighbouring stations
MIN_WIDTH = 0.004


def write_csv(path: Path, y_m: np.ndarray, z_m: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{y * 1e3:.6f},{z * 1e3:.6f}" for y, z in zip(y_m, z_m)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    case = json.loads(CASE_IN.read_text(encoding="utf-8"))
    right_index = next(i for i, t in enumerate(case["rail_templates"]) if t["id"] == "right")
    right = case["rail_templates"][right_index]
    stations = sorted(right["stations"], key=lambda item: item["s_m"])

    body_dir_rel = BODY_DIR.name
    # The stored station list repeats a few mileages; keep the copy that resolves
    # the most rail bodies, because the duplicate is the pre-split version.
    loaded: dict[float, tuple] = {}
    for item in stations:
        source = (BASE / item["profile"]["file"]).resolve()
        y, z = load_section(str(source))
        grid, env = envelope(y, z)
        comps = segment(grid, env)
        current = loaded.get(item["s_m"])
        if current is None or len(comps) > len(current[1]):
            loaded[item["s_m"]] = (item, comps, grid, env)

    order = sorted(loaded)
    chain: list[dict] = []
    report: list[dict] = []
    previous_crown = None
    chain_end = None
    for s_m in order:
        if s_m < S_FIRST:
            continue
        item, comps, grid, env = loaded[s_m]
        if len(comps) < 2:
            # The two heads have fused again: past this point the surviving head
            # is the single rail, so the split ends here.
            chain_end = s_m
            break
        if previous_crown is None:
            candidate = min(comps, key=lambda c: c["crown_y_m"])
        else:
            candidate = min(comps, key=lambda c: abs(c["crown_y_m"] - previous_crown))
            if abs(candidate["crown_y_m"] - previous_crown) > MATCH_DY:
                break
        i, j = candidate["i"], candidate["j"]
        if grid[j] - grid[i] < MIN_WIDTH:
            break
        tag = f"r{int(round(s_m * 1e4)):07d}"
        point_file = BODY_DIR / f"point_{tag}.csv"
        main_file = BODY_DIR / f"main_{tag}.csv"
        write_csv(point_file, grid[i:j + 1], env[i:j + 1])
        keep = np.r_[np.arange(0, i), np.arange(j + 1, len(grid))]
        write_csv(main_file, grid[keep], env[keep])
        chain.append({
            "s_m": s_m,
            "point_file": f"{body_dir_rel}/{point_file.name}",
            "main_file": f"{body_dir_rel}/{main_file.name}",
        })
        previous_crown = candidate["crown_y_m"]
        report.append({
            "s_m": s_m,
            "point_crown_y_mm": round(candidate["crown_y_m"] * 1e3, 3),
            "point_crown_z_mm": round(candidate["crown_z_m"] * 1e3, 3),
            "point_width_mm": round(candidate["width_m"] * 1e3, 2),
            "n_bodies": len(comps),
        })

    if len(chain) < 3:
        raise SystemExit(f"point-rail chain too short: {len(chain)} stations")
    if chain_end is None:
        raise SystemExit("the two heads never fused again; check the station list")

    lo, hi = chain[0]["s_m"], chain[-1]["s_m"]
    by_s = {entry["s_m"]: entry for entry in chain}

    main_stations = []
    for s_m in order:
        item = loaded[s_m][0]
        if s_m in by_s:
            main_stations.append({
                "s_m": s_m,
                "profile": {"file": by_s[s_m]["main_file"], "format": "csv", "units": "mm"},
                "id": item["id"],
            })
        elif s_m <= chain_end:
            main_stations.append(item)

    point_stations = [
        {"s_m": entry["s_m"],
         "profile": {"file": entry["point_file"], "format": "csv", "units": "mm"},
         "id": f"P{int(round(entry['s_m'] * 1e4))}"}
        for entry in chain
    ]
    # Past the frog the surviving head *is* the point rail, so it keeps carrying
    # the wheel on the original merged sections.
    point_stations += [loaded[s_m][0] for s_m in order if s_m > chain_end]

    bodies = [
        {"id": "main", "s_hi_m": hi, "stations": main_stations},
        {"id": "point", "s_lo_m": lo, "stations": point_stations},
    ]
    right_out = {key: value for key, value in right.items() if key != "stations"}
    right_out["bodies"] = bodies
    case["rail_templates"][right_index] = right_out

    CASE_OUT.write_text(json.dumps(case, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = {
        "schema": "velch-body-split-1",
        "case": CASE_OUT.name,
        "point_body_range_m": [lo, hi],
        "point_body_stations": len(chain),
        "point_width_mm_first_last": [report[0]["point_width_mm"], report[-1]["point_width_mm"]],
        "point_crown_y_mm_first_last": [report[0]["point_crown_y_mm"], report[-1]["point_crown_y_mm"]],
        "right_main_stations": len(main_stations),
        "report": report,
    }
    (BASE / "body_split_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"point body: {len(chain)} stations, s = {lo:.3f} .. {hi:.3f} m")
    print(f"  width  {report[0]['point_width_mm']:.2f} -> {report[-1]['point_width_mm']:.2f} mm")
    print(f"  crown  {report[0]['point_crown_y_mm']:.1f} -> {report[-1]['point_crown_y_mm']:.1f} mm")
    print(f"  two-body stations: {sum(1 for r in report if r['n_bodies'] >= 2)}")
    print(f"wrote {CASE_OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
