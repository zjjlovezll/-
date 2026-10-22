"""Break the penetration down per body at one mileage.

For a given case, station pair and sink, evaluate
``pen(y) = rail_z(y) - wheel_z(y)`` per rail body over the wheel/rail overlap
and report where each body's maximum sits.  This reproduces what
``find_graph_contact`` decides, so it shows *why* one body wins.

Usage: python probe_pen_breakdown.py <case.json> <s_m> [sink_mm ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parents[1] / "src"))

from velch.profiles import load_profile  # noqa: E402

RAIL_Y_OFFSET = 0.753


def spec_to_graph(spec: dict, *, surface: str):
    fmt = spec.get("format", "csv")
    units = spec.get("units", "m")
    scale = 1e-3 if units == "mm" else 1.0
    return load_profile(
        Path(spec["file"]),
        file_format=fmt,
        surface=surface,
        y_scale_m=scale,
        z_scale_m=scale,
        y_sign=int(spec.get("y_sign", 1)),
        z_sign=int(spec.get("z_sign", 1)),
        y_offset_m=float(spec.get("y_offset_m", 0.0)),
        z_offset_m=float(spec.get("z_offset_m", 0.0)),
    )


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    case_path = Path(argv[1])
    target = float(argv[2])
    sinks = [float(v) / 1e3 for v in argv[3:]] or [0.2e-3, 0.4628e-3, 0.9229e-3]
    case = json.loads(case_path.read_text(encoding="utf-8"))
    template = next(t for t in case["rail_templates"] if t.get("bodies"))
    wheel_spec = case["wheels"][0]["profile"]
    wheel = spec_to_graph(wheel_spec, surface="wheel_lower")
    wheel_lateral = float(case["wheels"][0].get("lateral_offset_m", 0.7465))
    if wheel_lateral < 0:
        wheel = next(w for w in case["wheels"] if float(w.get("lateral_offset_m", 0)) > 0)
        wheel_lateral = float(wheel.get("lateral_offset_m", 0.7465))
        wheel = spec_to_graph(wheel["profile"], surface="wheel_lower")
    print(f"wheel y=[{wheel.y_m.min() * 1e3:.1f},{wheel.y_m.max() * 1e3:.1f}] mm "
          f"z=[{wheel.z_m.min() * 1e3:.3f},{wheel.z_m.max() * 1e3:.3f}] mm "
          f"offset={wheel_lateral * 1e3:.2f}")
    for body in template["bodies"]:
        stations = sorted(body["stations"], key=lambda s: s["s_m"])
        pair = min(zip(stations, stations[1:]), key=lambda ab: abs(0.5 * (ab[0]["s_m"] + ab[1]["s_m"]) - target))
        lo, hi = pair
        w = (target - lo["s_m"]) / (hi["s_m"] - lo["s_m"])
        g_lo = spec_to_graph(lo["profile"], surface="rail_top")
        g_hi = spec_to_graph(hi["profile"], surface="rail_top")
        print(f"\nbody {body['id']}: stations {lo['s_m']:.4f}/{hi['s_m']:.4f} weight {w:.3f}")
        for sink in sinks:
            lo_y = max(g_lo.y_m.min(), g_hi.y_m.min(), wheel.y_m.min() + wheel_lateral)
            hi_y = min(g_lo.y_m.max(), g_hi.y_m.max(), wheel.y_m.max() + wheel_lateral)
            grid = np.linspace(lo_y, hi_y, 4000)
            rail = np.interp(grid, g_lo.y_m, g_lo.z_m) * (1 - w) + np.interp(grid, g_hi.y_m, g_hi.z_m) * w
            wz = np.interp(grid - wheel_lateral, wheel.y_m, wheel.z_m) + 0.430 - sink
            pen = rail - wz
            k = int(np.argmax(pen))
            print(f"   sink {sink * 1e3:5.3f} mm -> pen_max {pen[k] * 1e3:7.4f} mm at y {grid[k] * 1e3:8.2f} mm"
                  f"  (rail {rail[k] * 1e3:7.3f}, wheel {wz[k] * 1e3:7.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
