"""What the 67 % -> 18 % drop at 58.6 -> 58.8 m is, and what it is not.

Round 305 measured the effective gap at fourteen stations and said the share curve beyond 58.6 m stays
unquoted until that drop is explained.  Three candidates were left open: a station-table splice, the
blade body's lateral window ending, or a genuine crest feature.  This script decides between them with
geometry only -- no seats, no dynamics.

Three measurements:

1. the blade and stock crests at **every section** of the blade body between 58.0 and 59.3 m, which shows
   where the crest goes and which section carries the excursion;
2. the crest difference on a 0.02 m grid with its roughness against a 0.1 m trend, which separates a
   section-level feature from an interpolation artefact (a 0.12 m section pitch cannot produce roughness
   at 0.02 m unless the reader is doing something wrong);
3. the analytical sensitivity d(share)/dg near flush, which is what turns a tens-of-micrometre crest
   excursion into a tens-of-percent share swing.

Pre-registered reading (before looking at the numbers):

* a splice would show up as a break in the section-file numbering or in the station spacing;
* an interpolation artefact would show roughness at the grid scale, i.e. roughness comparable to the
  excursion itself;
* a section-level crest feature would show a smooth series with the excursion carried by the sections.

The crest difference of a section is defined the way round 305 defined it: stock crest minus blade crest,
both from the section's own `max(z)`, so a negative value means the blade sits above the stock.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

CASE = ROOT.parent / "scratch" / "s146" / "one_set_x46.json"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "crest_series.json"

RAIL = "axle1_right"
WINDOW_M = (58.0, 59.3)
FINE_STEP_M = 0.02
TREND_POINTS = 5

FROZEN_DEPTH_M = 65.4661e-6
WHEEL_LOAD_N = 481_078.5 / 8
CASE_WEIGHT_N = 481_078.5
CONTACTS = 8


def stiffness() -> float:
    return 59_680.57685863 / FROZEN_DEPTH_M ** 1.5


def crest_m(series, station_m: float) -> float:
    return float(np.nanmax(np.asarray(series.sample(station_m, 1.0).profile.z_m, float)))


def load_parts():
    from velch.vehicle import load_vehicle_case

    case = load_vehicle_case(CASE)
    rail = next(item for item in case.rails if item.id == RAIL)
    bodies = {str(body.id).split(":")[-1]: body for body in rail.bodies}
    raw = json.loads(CASE.read_text(encoding="utf-8"))
    template = next(item for item in raw["rail_templates"] if item.get("id") == "right")
    blade = next(body for body in template["bodies"] if body["id"] == "blade")
    return bodies, blade["stations"]


def section_rows(bodies, stations) -> list:
    rows = []
    for entry in stations:
        station = float(entry["s_m"])
        if not (WINDOW_M[0] <= station <= WINDOW_M[1]):
            continue
        rows.append({
            "station_m": station,
            "file": pathlib.Path(entry["profile"]["file"]).name,
            "blade_crest_m": crest_m(bodies["blade"].series, station),
            "stock_crest_m": crest_m(bodies["stock"].series, station),
        })
    for row in rows:
        row["gap_m"] = row["stock_crest_m"] - row["blade_crest_m"]
    return rows


def fine_series(bodies) -> dict:
    grid = np.arange(WINDOW_M[0] + 0.30, WINDOW_M[1] - 0.30 + 1e-9, FINE_STEP_M)
    gaps = np.array([crest_m(bodies["stock"].series, station) - crest_m(bodies["blade"].series, station)
                     for station in grid])
    trend = np.convolve(gaps, np.ones(TREND_POINTS) / TREND_POINTS, mode="same")[TREND_POINTS // 2:-(TREND_POINTS // 2)]
    residual = gaps[TREND_POINTS // 2:-(TREND_POINTS // 2)] - trend
    return {
        "grid_m": [float(value) for value in grid],
        "gap_m": [float(value) for value in gaps],
        "span_um": float((gaps.max() - gaps.min()) * 1e6),
        "roughness_rms_um": float(np.sqrt(np.mean(residual ** 2)) * 1e6),
        "roughness_max_um": float(np.abs(residual).max() * 1e6),
        "trend_points": TREND_POINTS,
    }


def sensitivity() -> dict:
    """d(share)/dg at flush, and the share swing a crest excursion produces."""
    depth = (WHEEL_LOAD_N / stiffness()) ** (2.0 / 3.0)

    def share(gap: float) -> float:
        stiff = stiffness()
        low, high = max(0.0, gap), 1.0e-3
        for _ in range(200):
            mid = 0.5 * (low + high)
            total = stiff * mid ** 1.5 + stiff * max(mid - gap, 0.0) ** 1.5
            if total < WHEEL_LOAD_N:
                low = mid
            else:
                high = mid
        depth_now = 0.5 * (low + high)
        return stiff * max(depth_now - gap, 0.0) ** 1.5 / WHEEL_LOAD_N

    derivative = -1.5 * depth ** 0.5 / depth ** 1.5
    return {
        "depth_m": float(depth),
        "d_share_d_gap_per_m": float(derivative),
        "d_share_d_gap_per_um": float(derivative * 1e-6),
        "share_at_minus_21um": share(-21.30e-6),
        "share_at_plus_18um": share(18.07e-6),
    }


def numbering(rows: list) -> dict:
    stems = []
    for row in rows:
        digits = row["file"].rsplit("-", 1)[-1].split(".")[0]
        stems.append(int(digits))
    gaps = np.diff([row["station_m"] for row in rows])
    return {
        "section_numbers": stems,
        "consecutive": bool(all(b - a == 1 for a, b in zip(stems, stems[1:]))),
        "station_gaps_min_m": float(gaps.min()),
        "station_gaps_max_m": float(gaps.max()),
    }


def measure() -> dict:
    bodies, stations = load_parts()
    rows = section_rows(bodies, stations)
    return {"sections": rows, "fine": fine_series(bodies), "sensitivity": sensitivity(),
            "numbering": numbering(rows)}


def verdict(data: dict) -> dict:
    rows = data["sections"]
    gaps = [row["gap_m"] for row in rows]
    peak_index = int(np.argmin(gaps))
    peak = rows[peak_index]
    neighbours = [row["gap_m"] for row in rows if abs(row["station_m"] - peak["station_m"]) <= 0.25]
    excursion = (max(neighbours) - min(neighbours)) if neighbours else 0.0
    return {
        "peak_section": peak["file"],
        "peak_station_m": peak["station_m"],
        "peak_gap_um": peak["gap_m"] * 1e6,
        "excursion_um": excursion * 1e6,
        "splice": not data["numbering"]["consecutive"],
        "interpolation_artefact": bool(data["fine"]["roughness_max_um"] > 10.0),
        "depth_um": data["sensitivity"]["depth_m"] * 1e6,
        "sensitivity_per_um": data["sensitivity"]["d_share_d_gap_per_um"],
    }


def main() -> int:
    data = measure()
    result = verdict(data)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"sections": data["sections"], "fine": data["fine"],
                                  "sensitivity": data["sensitivity"],
                                  "numbering": data["numbering"], "verdict": result},
                                 indent=2, sort_keys=True) + chr(10), encoding="utf-8")

    print(f"{'station':>8} {'file':34s} {'blade um':>9} {'stock um':>9} {'gap um':>8}")
    for row in data["sections"]:
        print(f"{row['station_m']:8.3f} {row['file']:34s} {row['blade_crest_m']*1e6:9.2f} "
              f"{row['stock_crest_m']*1e6:9.2f} {row['gap_m']*1e6:+8.2f}")
    print()
    fine = data["fine"]
    print(f"fine series {len(fine['grid_m'])} points at {FINE_STEP_M} m: gap span {fine['span_um']:.2f} um, "
          f"roughness vs {fine['trend_points']}-point trend rms {fine['roughness_rms_um']:.2f} um / "
          f"max {fine['roughness_max_um']:.2f} um")
    print(f"section numbering {data['numbering']['section_numbers']} consecutive "
          f"{data['numbering']['consecutive']}, station gaps "
          f"{data['numbering']['station_gaps_min_m']:.3f}-{data['numbering']['station_gaps_max_m']:.3f} m")
    sens = data["sensitivity"]
    print(f"flush depth {sens['depth_m']*1e6:.2f} um, d(share)/dg {sens['d_share_d_gap_per_um']:.4f} per um, "
          f"share at -21.3 um {sens['share_at_minus_21um']*100:.1f} %, at +18.1 um "
          f"{sens['share_at_plus_18um']*100:.1f} %")
    print(f"peak section {result['peak_section']} at {result['peak_station_m']:.3f} m, gap "
          f"{result['peak_gap_um']:+.2f} um, 0.5 m excursion {result['excursion_um']:.2f} um")
    print(f"splice {result['splice']}, interpolation artefact {result['interpolation_artefact']}")
    print(f"report -> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
