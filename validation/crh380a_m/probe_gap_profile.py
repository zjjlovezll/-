"""Quasi-static gap closure required by the sections, mile by mile.

At each station pair the wheel is put at the static stance (centre height
``R - sink``) and the penetration is evaluated per rail body.  The deepest
penetration ``pen_max`` over bodies gives the **gap closure** the wheel needs
before it touches anything:

    gap(s) = -pen_max(s)      (positive = the wheel has to drop this far)

Comparing ``gap(s)`` with Simpack's own wheelset vertical travel separates two
questions that are otherwise confused: whether the *sections* demand a big
drop, and whether our *dynamics* amplifies a small drop into a big force.

Usage: python probe_gap_profile.py <case.json> [s_lo s_hi ds_mm] [sink_mm]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parents[1] / "src"))

from velch.profiles import load_profile  # noqa: E402


def to_graph(spec: dict, surface: str):
    scale = 1e-3 if spec.get("units", "m") == "mm" else 1.0
    return load_profile(
        Path(spec["file"]), file_format=spec.get("format", "csv"), surface=surface,
        y_scale_m=scale, z_scale_m=scale,
        y_sign=int(spec.get("y_sign", 1)), z_sign=int(spec.get("z_sign", 1)),
        y_offset_m=float(spec.get("y_offset_m", 0.0)),
        z_offset_m=float(spec.get("z_offset_m", 0.0)),
    )


def main(argv: list[str]) -> int:
    case_path = Path(argv[1]) if len(argv) > 1 else BASE / "case_C_bodies.json"
    lo = float(argv[2]) if len(argv) > 2 else 79.20
    hi = float(argv[3]) if len(argv) > 3 else 82.60
    ds = (float(argv[4]) if len(argv) > 4 else 20.0) / 1e3
    sink = (float(argv[5]) if len(argv) > 5 else 0.4628) / 1e3
    case = json.loads(case_path.read_text(encoding="utf-8"))
    template = max(
        case["rail_templates"],
        key=lambda t: (len(t.get("stations", [])), len(t.get("bodies", []))),
    )
    bodes = template.get("bodies")
    if not bodes:
        bodes = [{"id": template.get("id", "rail"), "stations": template["stations"]}]
    wheel_case = next(w for w in case["wheels"] if float(w.get("lateral_offset_m", 0)) > 0)
    wheel = to_graph(wheel_case["profile"], "wheel_lower")
    lat = float(wheel_case["lateral_offset_m"])

    bodies = []
    for body in bodes:
        stations = sorted(body["stations"], key=lambda s: s["s_m"])
        bodies.append((body["id"], stations, [to_graph(st["profile"], "rail_top") for st in stations]))

    print(f"case {case_path.name}  sink {sink * 1e3:.3f} mm  grid {lo:.2f}..{hi:.2f} step {ds * 1e3:.0f} mm")
    print(f"  {'s_m':>7s} {'gap_mm':>8s} {'body':>6s} {'y_mm':>8s}")
    rows = []
    for s in np.arange(lo, hi + 1e-9, ds):
        best, where, at = -np.inf, "-", np.nan
        for name, stations, graphs in bodies:
            if not (stations[0]["s_m"] - 1e-9 <= s <= stations[-1]["s_m"] + 1e-9):
                continue
            idx = int(np.searchsorted([st["s_m"] for st in stations], s))
            idx = min(max(idx, 1), len(stations) - 1)
            a, b = stations[idx - 1], stations[idx]
            w = 0.0 if b["s_m"] == a["s_m"] else (s - a["s_m"]) / (b["s_m"] - a["s_m"])
            ga, gb = graphs[idx - 1], graphs[idx]
            lo_y = max(ga.y_m.min(), gb.y_m.min(), wheel.y_m.min() + lat)
            hi_y = min(ga.y_m.max(), gb.y_m.max(), wheel.y_m.max() + lat)
            if hi_y <= lo_y:
                continue
            grid = np.linspace(lo_y, hi_y, 3000)
            rail = np.interp(grid, ga.y_m, ga.z_m) * (1 - w) + np.interp(grid, gb.y_m, gb.z_m) * w
            wz = np.interp(grid - lat, wheel.y_m, wheel.z_m) + 0.430 - sink
            pen = rail - wz
            k = int(np.argmax(pen))
            if pen[k] > best:
                best, where, at = pen[k], name, grid[k]
        if np.isfinite(best):
            rows.append((s, -best * 1e3, where, at * 1e3))
            print(f"  {s:7.3f} {-best * 1e3:8.3f} {where:>6s} {at * 1e3:8.2f}")
    if rows:
        arr = np.asarray([(r[0], r[1]) for r in rows])
        print(f"\nmax gap {arr[:, 1].max():.3f} mm at s={arr[int(arr[:, 1].argmax()), 0]:.3f} m")
        print(f"mean gap {arr[:, 1].mean():.3f} mm over {arr.shape[0]} stations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
