"""Build the diverging-route case for 07(009) from the SDITT profile library.

Geometry provenance (read this before trusting any number here)
--------------------------------------------------------------
* **Rail shape** comes from the SDITT library files themselves (``qjbg`` curved stock rail,
  ``qjg_cgyg`` curved switch rail, ``cxg`` curved crossing).  Nothing about the section is invented.
* **Placement** cannot come from those files: each ``.prr`` lives in its own part frame, so the head
  centre of ``qjbg`` is not comparable with that of ``cxg`` (measured drift +72 / +34 / +29 mm, which
  would produce a non-monotone route if chained).  The route is therefore placed on the **drawing's
  design radius** R = 1100.7175 m (extracted from 瀹笓绾?07)009 DXF) with a smooth entry from the
  switch toe: ``y(s) = (s - s_toe)^2 / (2R)`` for ``s > s_toe``, zero before it.
* The leftover in each station's ``y_offset`` is the difference between that design placement and the
  file's own band centre, so the running band lands exactly on the route's rail position.

That split is the honest one available with this dataset: shape measured, placement from design.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
CATALOG = HERE.parent / "turnout18_ref" / "sditt_turnout_catalog.json"
REFERENCE = HERE / "case_Z_local_rail.json"
RAIL_HALF_GAUGE_M = 0.753
TOE_STATION_M = 50.578
DEFAULT_RADIUS_M = 1100.7175
STEP_M = 0.005

# which part carries the diverging route as a function of station
CHAIN = (("qjbg", 0.0, 60.943), ("qjg_cgyg", 50.578, 100.0), ("cxg", 103.280, 116.590))


def band_centre_mm(catalog: dict, station_key: str, part: str) -> float | None:
    record = catalog["stations"].get(station_key, {}).get(part)
    if record is None:
        return None
    low, high = record["y_mm"]
    return 0.5 * (float(low) + float(high))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--radius-m", type=float, default=DEFAULT_RADIUS_M)
    parser.add_argument("--output", default="case_diverging_R1100.json")
    parser.add_argument("--span", nargs=2, type=float, default=(45.0, 120.0))
    args = parser.parse_args()

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    template = json.loads(REFERENCE.read_text(encoding="utf-8"))
    stations = catalog["stations"]
    available = {part: sorted(float(k) for k in stations if part in stations[k]) for part, _, _ in CHAIN}

    def active_part(station_m: float) -> str | None:
        for part, low, high in CHAIN:
            if low - 1e-9 <= station_m <= high + 1e-9 and stations.get(f"{station_m:.3f}", {}).get(part):
                return part
        for part, low, high in CHAIN:
            if low - 1e-9 <= station_m <= high + 1e-9:
                values = available[part]
                if not values:
                    continue
                nearest = min(values, key=lambda s: abs(s - station_m))
                if abs(nearest - station_m) <= 1.0:
                    return part
        return None

    def nearest_file(part: str, station_m: float) -> str:
        values = available[part]
        nearest = min(values, key=lambda s: abs(s - station_m))
        return stations[f"{nearest:.3f}"][part]["file"]

    def route_offset_m(station_m: float) -> float:
        reach = station_m - TOE_STATION_M
        if reach <= 0.0:
            return 0.0
        return reach * reach / (2.0 * args.radius_m)

    lo, hi = args.span
    count = int(round((hi - lo) / STEP_M))
    entries = []
    known = []
    for index in range(count + 1):
        station_m = lo + index * STEP_M
        part = active_part(station_m)
        if part is None:
            continue
        path_m = route_offset_m(station_m)
        centre = band_centre_mm(catalog, f"{station_m:.3f}", part)
        if centre is None:
            values = available[part]
            nearest = min(values, key=lambda s: abs(s - station_m))
            centre = band_centre_mm(catalog, f"{nearest:.3f}", part)
        if centre is None:
            continue
        # The file's own band centre is removed so the running band lands on the standard
        # half-gauge line: the case works in the rail reference frame, not the through frame.
        known.append((station_m, RAIL_HALF_GAUGE_M + path_m - centre / 1000.0))

    if len(known) < 2:
        raise SystemExit("no stations resolved for the diverging route")

    # Second pass: the part handovers (60.943 -> 61.0, 100.0 -> 103.28) break the band centre, so the
    # *offset* is interpolated across them and every 5 mm station gets a real file.  Interpolating the
    # offset (not the band centre) keeps the running band on one continuous line, which is what the
    # contact search needs: adjacent stations must keep lateral overlap.
    known_s = [item[0] for item in known]
    known_o = [item[1] for item in known]
    for index in range(count + 1):
        station_m = lo + index * STEP_M
        part_for_file = None
        for part, low, high in CHAIN:
            if low - 1e-9 <= station_m <= high + 1e-9:
                part_for_file = part
                break
        if part_for_file is None:
            continue
        path_m = route_offset_m(station_m)
        offset = float(np.interp(station_m, known_s, known_o))
        stations_spec = {
            "s_m": round(station_m, 6),
            "id": f"div{index:05d}",
            "profile": {
                "file": nearest_file(part_for_file, station_m),
                "format": "prr",
                "units": "m",
                "y_sign": 1,
                "z_sign": -1,
                "y_offset_m": round(offset, 9),
            },
        }
        entries.append((station_m, part_for_file, path_m, offset, stations_spec))

    if not entries:
        raise SystemExit("no stations emitted for the diverging route")

    left_index = next((i for i, rail in enumerate(template["rail_templates"])
                       if rail.get("stations")), 0)
    left_profile = dict(template["rail_templates"][left_index]["stations"][0]["profile"])
    left_entries = []
    for index in range(count + 1):
        station_m = lo + index * STEP_M
        spec = dict(left_profile)
        spec["y_offset_m"] = round(-RAIL_HALF_GAUGE_M + route_offset_m(station_m), 9)
        left_entries.append({"s_m": round(station_m, 6), "id": f"lef{index:05d}", "profile": spec})

    template_case = dict(template)
    template_case["case_id"] = f"diverging_R{args.radius_m:.1f}"
    template_case["purpose"] = "engineering"
    template_case["purpose_detail"] = (
        "diverging route of turnout 18: rail shape from SDITT 07(009) parts, placement from the drawing design radius "
        f"R={args.radius_m} m entered from the switch toe at {TOE_STATION_M} m; single body per station "
        "(stock/switch panel transfer not yet modelled)")
    rails = [dict(t) for t in template["rail_templates"]]
    # The right rail is the template built from bodies (main / point / wing); the left one
    # carries a plain station list.  Select by that, not by an offset that a body-only
    # template does not have.
    right_index = next((i for i, rail in enumerate(rails) if rail.get("bodies")), 0)
    rails[left_index]["stations"] = left_entries
    rails[right_index]["stations"] = [entry[4] for entry in entries]
    rails[right_index].pop("bodies", None)
    print(f"  diverging stations written to rail_templates[{right_index}]")
    other = [i for i in range(len(rails)) if i != right_index]
    for index in other:
        if rails[index].get("stations"):
            rails[index].pop("bodies", None)
    template_case["rail_templates"] = rails
    template_case["path"] = {
        "stations_s_m": [round(entry[0], 6) for entry in entries],
        "y_m": [round(entry[2], 9) for entry in entries],
    }
    if "initial_state" in template_case:
        template_case.pop("initial_state", None)

    output = HERE / args.output
    output.write_text(json.dumps(template_case, indent=1), encoding="utf-8")

    parts_used: dict[str, int] = {}
    for _, part, _, _, _ in entries:
        parts_used[part] = parts_used.get(part, 0) + 1
    print(f"wrote {output.name}: {len(entries)} right-rail stations {lo:.1f}..{hi:.1f} m, "
          f"R={args.radius_m} m")
    print(f"  parts used: {parts_used}")
    print(f"  path at toe {entries[0][0]:.2f} m: {entries[0][2] * 1e3:+.3f} mm; "
          f"end {entries[-1][0]:.2f} m: {entries[-1][2] * 1e3:+.3f} mm "
          f"(max {max(e[2] for e in entries) * 1e3:+.3f} mm)")
    for station_m in (50.578, 55.0, 60.0, 61.0, 70.0, 80.0, 100.0, 103.5, 110.0, 116.5):
        entry = min(entries, key=lambda e: abs(e[0] - station_m))
        print(f"  {entry[0]:8.3f} m  {entry[1]:<10} path {entry[2] * 1e3:+8.3f} mm  "
              f"band centre {entry[3]:+8.2f} mm  y_offset {entry[4]['profile']['y_offset_m']:+.6f} m")

    from velch.vehicle import load_vehicle_case  # noqa: PLC0415  (import after writing the file)

    case = load_vehicle_case(output)
    print(f"\nloaded: {case.case_id}, {len(case.rails)} rails, "
          f"{sum(len(r.contact_bodies) for r in case.rails)} bodies, "
          f"path {case.path.summary() if case.path else 'none'}")
    right = [rail for rail in case.rails if rail.id.endswith("right")]
    for rail in right[:2]:
        for body in rail.contact_bodies:
            print(f"  {rail.id}/{body.id}: {len(body.series._stations)} stations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

