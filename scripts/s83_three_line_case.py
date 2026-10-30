"""Build the straight turnout case out of SDITT's three rail lines, with no z-offset table anywhere.

SDITT drives a turnout as several independent rail lines, each with its own mileage table; contact is
evaluated per line and the wheel sits on the deepest, so the load transfers by geometry alone.  This
script reproduces that structure in our case format:

  right rail, three bodies
    stock  (07(009)-Mileage-qjbg.txt)          curved stock rail, the running surface throughout
    blade  (07(009)-Mileage-zjg_zgyg_250722)   straight switch blade + wing rail
    point  (07(009)-Mileage-cxg.txt)           long point rail

Lateral datum: a line's section is expressed in its own frame, so each station's `y_offset_m` is chosen so
that its **crown** lands on the same track-relative `y` as the stock rail's crown at that mileage.  That is
the physical requirement -- where two lines overlap they must present one running surface -- and it is why
nothing has to be handed to the solver as a lowering table: the blade's crown is simply 14.94 mm lower in
z, which is what the section file already says.

z is passed through with `z_sign = -1` because these sections store z growing downward (crown at 0).

Run: PYTHONPATH=src python -X utf8 scripts/s83_three_line_case.py [--seat]
"""
from __future__ import annotations

import argparse
import json
import importlib.util
from pathlib import Path
import re
import sys

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
POINT = re.compile(r"^\s*(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s*$")
BASE_CASE = SCRIPT_DIR.parents[1] / "scratch" / "s30" / "case_diverging_gauge.json"
OUT_DIR = SCRIPT_DIR.parents[1] / "scratch" / "s83"


def _s81():
    spec = importlib.util.spec_from_file_location("s81_lines", SCRIPT_DIR / "s81_sditt_lines.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["s81_lines"] = module
    spec.loader.exec_module(module)
    return module


def profile_geometry(path: Path) -> tuple[float, float]:
    """(crown y in mm, crown z in mm) of a section, in its own coordinates."""
    ys: list[float] = []
    zs: list[float] = []
    inside = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "point.begin" in line:
            inside = True
            continue
        if "point.end" in line:
            break
        if not inside or line.lstrip().startswith("!"):
            continue
        match = POINT.match(line)
        if match:
            ys.append(float(match.group(1)))
            zs.append(float(match.group(2)))
    array_y = np.array(ys)
    array_z = np.array(zs)
    index = int(np.argmin(array_z))
    return float(array_y[index]) * 1e3, float(array_z[index]) * 1e3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seat", action="store_true", help="seat the built case and print the loads")
    parser.add_argument("--seat-at", type=float, default=45.0)
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    parser.add_argument("--crown-gauge", type=float, default=1.493,
                        help="separation of the two rail crowns, = the wheel centre spacing")
    options = parser.parse_args()

    s81 = _s81()
    index = s81.section_index()
    case = json.loads(BASE_CASE.read_text(encoding="utf-8"))
    right = next(tpl for tpl in case["rail_templates"] if tpl["id"] == "right")
    left = next(tpl for tpl in case["rail_templates"] if tpl["id"] == "left")

    # Crown datum, set explicitly and symmetrically.  The inherited case put the right crown at +733.45 mm
    # while the left one sat at -759.89 mm: the pair's midpoint was 13.2 mm off the wheels' centreline, so
    # the right wheel rode 13-17 mm inside the gauge corner and the left wheel found no contact at all.
    # The physical requirement is that each crown sits directly under its wheel centre, i.e. at
    # +-(crown_gauge/2) with crown_gauge = the wheel centre spacing.
    half = options.crown_gauge / 2.0
    target_crown_m = +half
    print(f"case  {case['case_id']}")
    print(f"crown datum: each crown at +-{half*1e3:.1f} mm (crown gauge {options.crown_gauge:.4f} m), "
          f"so the pair is centred on the wheels' centreline")
    for template in (left, right):
        side = +1.0 if template["id"] == "right" else -1.0
        for station in template["stations"]:
            sign = float(station["profile"].get("y_sign", 1.0))
            crown_y_mm, _ = profile_geometry(Path(station["profile"]["file"]))
            station["profile"]["y_offset_m"] = float(side * half - sign * crown_y_mm * 1e-3)
        print(f"  template {template['id']:5s} recentred: y_offset now "
              f"{template['stations'][0]['profile']['y_offset_m']:+.6f} .. "
              f"{template['stations'][-1]['profile']['y_offset_m']:+.6f} m")

    bodies = []
    for name, table in s81.TABLES:
        rows = s81.read_table(s81.TABLE_DIR / table, index)
        unique: dict[float, object] = {}
        for row in rows:
            unique.setdefault(round(row.station_m, 6), row)
        rows = sorted(unique.values(), key=lambda r: r.station_m)
        stations = []
        for row in rows:
            crown_y_mm, crown_z_mm = profile_geometry(row.section)
            # y_sign = +1 for this side, so y_offset puts the crown on the stock crown's lateral position
            y_offset = target_crown_m - crown_y_mm * 1e-3
            stations.append({
                "id": f"{name}_{row.station_m:.3f}",
                "s_m": float(row.station_m),
                "profile": {
                    "file": str(row.section),
                    "format": "prr",
                    "units": "m",
                    "y_sign": 1,
                    "z_sign": -1,
                    "y_offset_m": float(y_offset),
                },
                "_crown_mm": crown_z_mm,
            })
        span = (stations[0]["s_m"], stations[-1]["s_m"])
        crowns = np.array([s["_crown_mm"] for s in stations])
        print(f"  body {name:9s} {len(stations):4d} stations {span[0]:8.3f}..{span[1]:8.3f} m  "
              f"crown z {crowns.min():+6.2f}..{crowns.max():+6.2f} mm  "
              f"y_offset {stations[0]['profile']['y_offset_m']:+.6f}..{stations[-1]['profile']['y_offset_m']:+.6f} m")
        for station in stations:
            station.pop("_crown_mm")
        bodies.append({"id": name, "s_lo_m": span[0], "s_hi_m": span[1], "stations": stations})

    # the case's run ends at 116.59 m, so clip the stock/point tails that run to 1000 m
    for body in bodies:
        kept = [s for s in body["stations"] if s["s_m"] <= 116.59 + 1e-9]
        if not kept:
            print(f"  ERROR body {body['id']} has no station inside the run")
            return 3
        body["stations"] = kept
        body["s_hi_m"] = min(body["s_hi_m"], 116.59)

    right["bodies"] = [
        {"id": body["id"], "s_lo_m": body["s_lo_m"], "s_hi_m": body["s_hi_m"], "stations": body["stations"]}
        for body in bodies
    ]
    right["stations"] = []
    case["case_id"] = "straight_three_lines_sditt"
    # `purpose` is a validated enum (synthetic|engineering); the description goes in purpose_detail.
    case["purpose"] = "engineering"
    case["purpose_detail"] = (
        "right rail carries three bodies (stock qjbg, blade+wing zjg_zgyg, point cxg) taken verbatim from "
        "07(009)-Mileage; no z-offset table, the blade's 14.94 mm is its own section geometry"
    )
    case["run"]["x_start_m"] = 30.0
    case["run"]["duration_s"] = 0.02
    case["run"]["output_step_s"] = 0.02
    case["run"].setdefault("seat_x_start_m", 45.0)
    case["run"]["seat_x_start_m"] = options.seat_at
    case.pop("initial_state", None)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "case_straight_three_lines.json"
    out.write_text(json.dumps(case, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {out}  ({out.stat().st_size/1e6:.2f} MB)")

    if not options.seat:
        return 0

    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics, _seat

    loaded = load_vehicle_case(out)
    dynamics = VehicleDynamics(loaded)
    print(f"\ncoordinates {dynamics.dimension}  rails {len(loaded.rails)}  "
          f"bodies per rail {[len(r.bodies) if hasattr(r, 'bodies') else 1 for r in loaded.rails]}")
    q = np.zeros(dynamics.dimension)
    v = np.zeros(dynamics.dimension)
    q, _ = _seat(loaded, dynamics, q, v)
    velocity = np.zeros(dynamics.dimension)
    radius = loaded.vehicle.nominal_wheel_radius_m
    speed = options.speed_kmh / 3.6
    for body in dynamics.topology.bodies:
        if body.id.startswith("wheelset"):
            velocity[dynamics.topology.require(body.id, "spin")] = speed / radius
    dynamics.placement_enabled = True
    dynamics.evaluate(0.0, q, velocity)
    even = 59662.0
    print(f"  {'rail':14s} {'N (kN)':>10s} {'x share':>8s} {'pen (um)':>10s} {'lever_y':>9s}")
    loaded_count = 0
    for rail in loaded.rails:
        response = dynamics.body_contacts.get(rail.id)
        if response is None or response.geometry is None:
            print(f"  {rail.id:14s} {'no geometry':>10s}")
            continue
        normal = response.normal_force_n
        if normal > 0:
            loaded_count += 1
        print(f"  {rail.id:14s} {normal/1e3:10.2f} {normal/even:8.3f} "
              f"{response.geometry.penetration_m*1e6:10.2f} {response.geometry.lever_y_m:+9.4f}")
    print(f"  loaded {loaded_count} of {len(loaded.rails)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
