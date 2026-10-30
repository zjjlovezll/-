"""M3: which reading of "the blade reaches the running surface" is the true one, and why.

Five stations have been quoted for the same physical event on the same turnout:

    57.733 m   the drawn sections, gap = the static penetration (65.4661 um)   scripts/s98
    58.423 m   the drawn sections, the two crowns level                        scripts/s98
    57.019 m   the SDITT mileage table, blade flush                            docs/SDITT_*
    64.900 m   lowering interpolated from three width anchors (3/30/72 mm)      scripts/s85 (retired)
    68.160 m   the old pre-registered value (design table 23 mm, 5.428 m ramp)  docs/TASKBOOK

This script computes every one of them from the same two sources -- the mileage tables and the drawn
sections -- so the disagreement has to be arithmetic, not opinion.  The measurement that decides it
is the width: at the station where the sections put the blade within one static penetration of the
stock, how wide is the blade, and what does the three-anchor table claim the lowering is there?

    d(s) = lowering(s)                [mm, positive = the blade sits below the stock]
    gap(s) = blade crown - stock crown = -d(s) + datum wobble (|datum| <= 0.07 mm)
    the blade touches at  d(s) = 0.0654661 mm

The three anchors are (3 mm, 14.94), (30 mm, 1.16), (72 mm, -0.09).  Between 30 and 72 mm a straight
line through those two anchors is the only thing the table can say; the sections say something else,
because the lowering is convex in the first metres and the width grows fastest exactly there.

    PYTHONPATH=src python -X utf8 scripts/s110_lowering_readings.py [--write]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

import numpy as np

from velch.vehicle import load_vehicle_case

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s110"
RAIL = "axle1_right"
STATIC_PENETRATION_M = 65.4661e-6
STEP_M = 0.002
#: The three anchors the retired reading interpolated through (width mm -> lowering mm).
ANCHORS = ((3.0, 14.94), (30.0, 1.16), (72.0, -0.09))
#: The old pre-registered value and the SDITT mileage-table value, quoted for the record only.
QUOTED = {"old_preregistered_m": 68.160, "sditt_flush_m": 57.019, "retired_interpolated_m": 64.900}
#: The per-station z-offsets the retired builder wrote (round 239 measured them on the case), keyed
#: by mileage.  This is the table whose *tail* was interpolated linearly to get 64.900 m: its last
#: two anchors are 60.047 m (+0.178 mm) and 70.848 m (-0.090 mm), both on the flat part, so a
#: straight line between them crosses 65.4661 um almost five metres too late.
RETIRED_OFFSET_TABLE = ((50.578, 14.940), (52.119, 10.857), (55.008, 3.201),
                        (57.019, 0.922), (60.047, 0.178), (70.848, -0.090))

_WIDTH = re.compile(r"-(\d+(?:\.\d+)?)\.txt$")


def width_mm_of(name: str) -> float:
    match = _WIDTH.search(name)
    # Past the ramp the blade body keeps running on the plain stock section (``jbg-...-R.txt``),
    # which carries no width.  Those stations are not part of the widening and are skipped.
    return float(match.group(1)) if match else float("nan")


def crown_m(series, station_m: float) -> float:
    return float(np.max(np.asarray(series.sample(station_m, 1.0).profile.z_m, dtype=float)))


def three_anchor_lowering_mm(width_mm):
    """Lowering the three anchors imply, in mm; accepts a scalar or an array of widths."""
    widths = [anchor[0] for anchor in ANCHORS]
    values = [anchor[1] for anchor in ANCHORS]
    return np.interp(width_mm, widths, values)


def first_crossing(stations: np.ndarray, values: np.ndarray, target: float, decreasing=True) -> float:
    """First station where ``values`` passes ``target``; ``decreasing`` picks the direction."""
    hit = np.nonzero(values <= target)[0] if decreasing else np.nonzero(values >= target)[0]
    return float(stations[int(hit[0])]) if hit.size else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    case = load_vehicle_case(CASE)
    rail = next(item for item in case.rails if item.id == RAIL)
    bodies = {body.id: body for body in rail.contact_bodies}
    stock, blade = bodies["stock"], bodies["blade"]
    low = float(blade.series.lowest_m)
    high = min(float(blade.series.highest_m), low + 30.0)
    stations = np.arange(low, high, STEP_M)

    # Widths come from the case's own station table, not from the sampled object: the station file
    # name is the only place the blade width is written down, and it must not be inferred.
    raw = json.loads(CASE.read_text(encoding="utf-8"))
    widths: dict[float, float] = {}
    for template in raw["rail_templates"]:
        if str(template.get("id", "")) != str(rail.template_id):
            continue
        for body in template.get("bodies", ()):
            if str(body.get("id")) != "blade":
                continue
            for station in body["stations"]:
                value = width_mm_of(str(station["profile"]["file"]))
                if np.isfinite(value):
                    widths[round(float(station["s_m"]), 6)] = value
    if not widths:
        raise SystemExit("no blade stations in the case; run scripts/s101_one_set_case.py first")

    rows = []
    for station in stations:
        nearest = min(widths, key=lambda value: abs(value - float(station)))
        if abs(nearest - float(station)) > STEP_M:
            continue
        rows.append({
            "s_m": float(station),
            "width_mm": widths[nearest],
            "blade_crown_m": crown_m(blade.series, float(station)),
            "stock_crown_m": crown_m(stock.series, float(station)),
        })
    stations = np.array([row["s_m"] for row in rows])
    width = np.array([row["width_mm"] for row in rows])
    gap = np.array([row["blade_crown_m"] - row["stock_crown_m"] for row in rows])
    #: lowering d(s) = -(gap), i.e. how far below the stock the blade crown sits, positive down.
    lowering = -gap

    touch = first_crossing(stations, lowering, STATIC_PENETRATION_M)
    flush = first_crossing(stations, lowering, 0.0)
    #: The retired reading: interpolate the widening, not the sections.
    lowering_three = np.interp(width, [a[0] for a in ANCHORS], [a[1] for a in ANCHORS]) * 1e-3
    touch_three = first_crossing(stations, lowering_three, STATIC_PENETRATION_M)
    flush_three = first_crossing(stations, lowering_three, 0.0)

    touch_index = int(np.argmin(np.abs(stations - touch)))
    table_s = np.array([anchor[0] for anchor in RETIRED_OFFSET_TABLE])
    table_d = np.array([anchor[1] for anchor in RETIRED_OFFSET_TABLE]) * 1e-3
    # The table was interpolated linearly between its anchors, so interpolate it: picking the first
    # anchor below the threshold would report the last anchor (70.848 m) instead of the crossing
    # inside the segment (measured 64.578 m, which is the 64.900 m that was quoted).
    grid = np.arange(table_s[0], table_s[-1], STEP_M)
    touch_table = first_crossing(grid, np.interp(grid, table_s, table_d), STATIC_PENETRATION_M)
    at_touch = rows[touch_index]
    d_three_at_touch = three_anchor_lowering_mm(at_touch["width_mm"]) * 1e-3
    overestimate_mm = (d_three_at_touch - STATIC_PENETRATION_M) * 1e3

    print(f"source: {RAIL} blade + stock, {len(rows)} stations from {low:.3f} m, step {STEP_M*1e3:.0f} mm")
    print(f"tip: width {width[0]:.1f} mm   lowering {lowering[0]*1e3:+.3f} mm")
    print()
    print("readings of 'the blade reaches the running surface':")
    print(f"  sections, first touch (65.4661 um)      {touch:8.3f} m")
    print(f"  sections, crowns level                  {flush:8.3f} m")
    print(f"  three-anchor interpolation, first touch {touch_three:8.3f} m")
    print(f"  three-anchor interpolation, level       {flush_three:8.3f} m")
    print(f"  retired mileage table, first touch      {touch_table:8.3f} m")
    for name, value in QUOTED.items():
        print(f"  quoted: {name:<32}{value:8.3f} m")
    print()
    print(f"at the sections' first touch ({touch:.3f} m):")
    print(f"  blade width {at_touch['width_mm']:.2f} mm   sections say lowering "
          f"{lowering[touch_index]*1e3:+.4f} mm")
    print(f"  three-anchor table says lowering {d_three_at_touch*1e3:+.3f} mm "
          f"=> overestimates by {overestimate_mm:+.3f} mm")
    print(f"retired mileage table crossing {touch_table:.3f} m, i.e. {touch_table - touch:+.3f} m")
    print()
    print("width and lowering along the ramp:")
    for probe in (50.578, 51.0, 52.0, 53.0, 55.0, touch, 60.0, 64.9, 68.16):
        if not (low <= probe <= high):
            continue
        index = int(np.argmin(np.abs(stations - probe)))
        print(f"  s {stations[index]:8.3f} m   width {width[index]:6.2f} mm   "
              f"lowering {lowering[index]*1e3:+8.3f} mm   three-anchor {lowering_three[index]*1e3:+8.3f} mm")

    verdict = ("the sections decide it: both retired readings interpolate a table instead of the "
               "drawn sections, and both land late -- the width table by "
               f"{touch_three - touch:.3f} m, the mileage table by {touch_table - touch:.3f} m")
    print()
    print(f"VERDICT: {verdict}")

    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        payload = {
            "rail": RAIL,
            "sections": {"first_touch_m": touch, "flush_m": flush},
            "three_anchor": {"first_touch_m": touch_three, "flush_m": flush_three,
                             "anchors": ANCHORS},
            "retired_mileage_table": {"first_touch_m": touch_table,
                                      "anchors": RETIRED_OFFSET_TABLE},
            "quoted": QUOTED,
            "at_first_touch": {"s_m": touch, "blade_width_mm": at_touch["width_mm"],
                               "sections_lowering_mm": float(lowering[touch_index] * 1e3),
                               "three_anchor_lowering_mm": d_three_at_touch * 1e3,
                               "overestimate_mm": overestimate_mm},
            "verdict": verdict,
            "profile": [
                {"s_m": float(stations[index]), "width_mm": float(width[index]),
                 "lowering_mm": float(lowering[index] * 1e3),
                 "three_anchor_mm": float(lowering_three[index] * 1e3)}
                for index in range(0, len(stations), max(1, len(stations) // 400))
            ],
        }
        (OUT / "readings.json").write_text(
            json.dumps(payload, indent=1, ensure_ascii=False) + chr(10), encoding="utf-8")
        print(f"report -> {OUT / 'readings.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
