"""Pre-flight diagnostic: per-axle/per-side contact depth for the CRH380A_M case.

Replicates the loader's profile transforms and the graph contact search so an
inactive or misaligned wheel/rail pair can be identified before a run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

VEH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(VEH / "src"))

from velch.contact import find_graph_contact  # noqa: E402
from velch.profiles import GraphProfile, ProfileSeries, Station, load_profile  # noqa: E402


def graph(spec: dict, surface: str) -> GraphProfile:
    return load_profile(Path(spec["file"]), file_format=spec["format"], surface=surface,
                        y_sign=int(spec.get("y_sign", 1)), z_sign=int(spec.get("z_sign", 1)),
                        y_offset_m=float(spec.get("y_offset_m", 0.0)),
                        z_offset_m=float(spec.get("z_offset_m", 0.0)))


def main() -> int:
    case_path = Path(sys.argv[1]) if len(sys.argv) > 1 else VEH / "validation/crh380a_m/case_A_plain.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    veh = case["vehicle"]
    wheels = {w["id"]: w for w in case["wheels"]}
    wheel_graph = {wid: graph(w["profile"], "wheel_lower") for wid, w in wheels.items()}
    for wid, g in wheel_graph.items():
        print(f"wheel {wid}: y[{g.y_m[0]*1e3:8.3f},{g.y_m[-1]*1e3:8.3f}] mm  z[{g.z_m.min()*1e3:7.3f},{g.z_m.max()*1e3:7.3f}] mm  "
              f"offset {wheels[wid]['lateral_offset_m']*1e3:8.3f} mm")
    print()
    for wid, g in wheel_graph.items():
        abs_y = g.y_m + wheels[wid]["lateral_offset_m"]
        print(f"wheel {wid}: absolute y[{abs_y[0]*1e3:8.3f},{abs_y[-1]*1e3:8.3f}] mm")
    print()

    offsets = [0.0] * 4
    bh = veh["bogie_half_spacing_m"]
    wh = veh["wheelbase_m"] / 2
    offsets = [bh + wh, bh - wh, -bh + wh, -bh - wh]
    x_start = case["run"]["x_start_m"]
    print(f"axle x positions: {[round(x_start + o, 3) for o in offsets]}")
    print()

    for tpl in case["rail_templates"]:
        stations = [Station(float(s["s_m"]), graph(s["profile"], "rail_top"), s["id"]) for s in tpl["stations"]]
        series = ProfileSeries(stations, tpl.get("event_branches"))
        wid = tpl["wheel_id"]
        wg = wheel_graph[wid]
        print(f"=== rail {tpl['id']} (wheel {wid}) stations {len(stations)} ===")
        sample_probe = None
        for i, off in enumerate(offsets):
            x = x_start + off
            sample = series.sample(x, 1)
            rp = sample.profile
            rail_y = rp.y_m
            print(f"  axle {i} x={x:8.3f} rail y[{rail_y[0]*1e3:8.3f},{rail_y[-1]*1e3:8.3f}] mm  "
                  f"z[{rp.z_m.min()*1e3:7.3f},{rp.z_m.max()*1e3:7.3f}] mm  ids={sample.selected_ids}")
            if sample_probe is None:
                sample_probe = (x, sample)
        x, sample = sample_probe
        zc = veh["wheel_center_height_m"]
        print(f"  --- depth sweep at x={x:.3f}, wheel_center={zc} ---")
        for sink in (0.0, 1e-4, 2e-4, 2.5e-4, 4e-4, 1e-3):
            geo = find_graph_contact(wg, sample, wheel_y_m=0.0, wheel_z_m=zc - sink,
                                     wheel_roll_rad=0.0,
                                     wheel_lateral_offset_m=wheels[wid]["lateral_offset_m"],
                                     rail_y_m=0.0, rail_z_m=0.0)
            if geo is None:
                print(f"    sink {sink*1e3:7.4f} mm -> no lateral overlap")
            else:
                print(f"    sink {sink*1e3:7.4f} mm -> y={geo.y_m*1e3:8.3f} mm depth={geo.penetration_m*1e3:7.4f} mm "
                      f"slope={geo.normal_y/geo.normal_z:8.4f} edge={geo.edge_limited} "
                      f"F={2.149e10*max(geo.penetration_m,0)**1.5/1e3:8.2f} kN")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
