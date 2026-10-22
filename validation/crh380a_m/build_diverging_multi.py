"""Assemble the diverging route with the switch panel as **two** rails, not one.

Why this exists
---------------
The first diverging case put a single body per station and produced 102.5 kN on the right rail at the
60.943 m handover.  In the real turnout the panel 50.578..60.943 m carries the curved stock rail
(``qjbg``) *and* the curved switch rail (``qjg_cgyg``) side by side -- roughly 46 mm apart at 53 m --
and the wheel transfers from one to the other.  Velch already has that machinery (``RailBody`` with
``s_lo_m``/``s_hi_m``); this script feeds it.

Placement rule (the one subtlety)
---------------------------------
Bands must **not** each be normalised onto the standard half-gauge line: that would stack the two rails
on top of each other.  Instead every body at a station shares one offset computed from the *stock*
rail's band centre, so the pair keeps the file's own relative spacing:

    offset(station) = 0.753 + y_route(station) - centre(stock, station) / 1000

At the frog (>= 103.28 m) there is no stock rail, so the active part's own centre is the reference.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
CATALOG = HERE.parent / "turnout18_ref" / "sditt_turnout_catalog.json"
REFERENCE = HERE / "case_Z_local_rail.json"
HALF_GAUGE_M = 0.753
TOE_STATION_M = 50.578
STOCK_END_M = 60.943
SWITCH_END_M = 100.0
FROG_START_M = 103.280
DEFAULT_RADIUS_M = 1100.7175
STEP_M = 0.005


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--radius-m", type=float, default=DEFAULT_RADIUS_M)
    parser.add_argument("--span", nargs=2, type=float, default=(30.0, 125.0))
    parser.add_argument("--output", default="case_diverging_multi.json")
    args = parser.parse_args()

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    stations = catalog["stations"]
    available = {part: sorted(float(k) for k in stations if part in stations[k])
                 for part in ("qjbg", "qjg_cgyg", "cxg")}

    def centre(part: str, station_m: float) -> tuple[float, str]:
        key = f"{station_m:.3f}"
        if key in stations and part in stations[key]:
            low, high = stations[key][part]["y_mm"]
            return 0.5 * (float(low) + float(high)), stations[key][part]["file"]
        nearest = min(available[part], key=lambda s: abs(s - station_m))
        low, high = stations[f"{nearest:.3f}"][part]["y_mm"]
        return 0.5 * (float(low) + float(high)), stations[f"{nearest:.3f}"][part]["file"]

    def route_offset_m(station_m: float) -> float:
        reach = station_m - TOE_STATION_M
        return 0.0 if reach <= 0.0 else reach * reach / (2.0 * args.radius_m)

    lo, hi = args.span
    count = int(round((hi - lo) / STEP_M))
    stock_stations, switch_stations, frog_stations, left_stations, path_pairs = [], [], [], [], []
    stock_end_offset, stock_end_path = 0.0, 0.0

    template = json.loads(REFERENCE.read_text(encoding="utf-8"))
    left_template_index = next(i for i, rail in enumerate(template["rail_templates"])
                               if rail.get("stations"))
    right_template_index = next(i for i, rail in enumerate(template["rail_templates"])
                                if rail.get("bodies"))
    left_profile = dict(template["rail_templates"][left_template_index]["stations"][0]["profile"])

    for index in range(count + 1):
        station_m = lo + index * STEP_M
        path_m = route_offset_m(station_m)
        path_pairs.append([round(station_m, 6), round(path_m, 9)])

        spec = dict(left_profile)
        spec["y_offset_m"] = round(-HALF_GAUGE_M + path_m, 9)
        left_stations.append({"s_m": round(station_m, 6), "id": f"L{index:05d}", "profile": spec})

        has_stock = station_m <= STOCK_END_M and station_m >= available["qjbg"][0]
        has_switch = TOE_STATION_M - 1e-9 <= station_m <= SWITCH_END_M
        has_frog = station_m >= FROG_START_M - 1e-9

        reference = None
        if has_stock:
            reference, _ = centre("qjbg", station_m)
        elif has_switch:
            reference, _ = centre("qjg_cgyg", station_m)
        elif has_frog:
            reference, _ = centre("cxg", station_m)
        if reference is None:
            continue
        # One offset per station, taken from the running rail (stock while it exists, else the switch
        # rail): the pair then keeps the file's own spacing, and the running surface stays on the
        # route line across the 60.943 m handover.
        offset = HALF_GAUGE_M + path_m - reference / 1000.0

        if has_stock:
            value, file = centre("qjbg", station_m)
            stock_stations.append({"s_m": round(station_m, 6), "id": f"S{index:05d}",
                                   "profile": {"file": file, "format": "prr", "units": "m",
                                               "y_sign": 1, "z_sign": -1,
                                               "y_offset_m": round(offset, 9)}})
        if has_switch:
            value, file = centre("qjg_cgyg", station_m)
            switch_stations.append({"s_m": round(station_m, 6), "id": f"W{index:05d}",
                                    "profile": {"file": file, "format": "prr", "units": "m",
                                                "y_sign": 1, "z_sign": -1,
                                                "y_offset_m": round(offset, 9)}})
        if has_frog:
            value, file = centre("cxg", station_m)
            frog_stations.append({"s_m": round(station_m, 6), "id": f"F{index:05d}",
                                  "profile": {"file": file, "format": "prr", "units": "m",
                                              "y_sign": 1, "z_sign": -1,
                                              "y_offset_m": round(offset, 9)}})

    bodies = []
    for name, entries, s_lo, s_hi in (("stock", stock_stations, float("-inf"), STOCK_END_M),
                                      ("switch", switch_stations, TOE_STATION_M, SWITCH_END_M),
                                      ("frog", frog_stations, FROG_START_M, float("inf"))):
        if entries:
            bodies.append({"id": name, "s_lo_m": s_lo, "s_hi_m": s_hi, "stations": entries})
            print(f"  body {name:<7} {len(entries):>5} stations  "
                  f"{entries[0]['s_m']:8.3f}..{entries[-1]['s_m']:8.3f} m")

    case = dict(template)
    case["case_id"] = f"diverging_multi_R{args.radius_m:.1f}"
    case["purpose"] = "engineering"
    case["purpose_detail"] = ("18 turnout diverging route: stock/switch/frog rails placed from the "
                              f"SDITT 07(009) library with design radius R={args.radius_m} m")
    rails = [dict(rail) for rail in template["rail_templates"]]
    rails[left_template_index]["stations"] = left_stations
    rails[left_template_index].pop("event_branches", None)
    rails[right_template_index]["bodies"] = bodies
    rails[right_template_index].pop("stations", None)
    # The template's event_branches point at station ids (R026/R027/...) that no longer exist in the
    # rebuilt station list; a dangling branch silently selects the wrong profile, which showed up as a
    # 16 mm penetration.  The zones are expressed by the body station sets instead.
    rails[right_template_index].pop("event_branches", None)
    case["rail_templates"] = rails
    case["path"] = {"stations_s_m": [p[0] for p in path_pairs], "y_m": [p[1] for p in path_pairs]}
    case.pop("initial_state", None)

    output = HERE / args.output
    output.write_text(json.dumps(case, indent=1), encoding="utf-8")

    from velch.vehicle import load_vehicle_case  # noqa: PLC0415

    loaded = load_vehicle_case(output)
    print(f"\nwrote {output.name}: {len(case['path']['y_m'])} path stations "
          f"({path_pairs[0][0]:.1f}..{path_pairs[-1][0]:.1f} m)")
    for rail in loaded.rails:
        if rail.id.endswith("right"):
            print(f"  {rail.id}: {[body.id for body in rail.contact_bodies]} "
                  f"({sum(len(body.series._stations) for body in rail.contact_bodies)} stations)")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
