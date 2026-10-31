"""Does the split law move with mileage?  Measure sigma as a function of "height above flush".

Round 254 measured the split law at one station (58.0 m) by lifting the whole blade body through a grid of
absolute offsets.  That grid is only meaningful near the transfer: at 52 m the blade sits about 7 mm down, so
a +-250 um lift never reaches it.  The physically meaningful coordinate is therefore not an absolute offset
but the blade's height **relative to flush**, ``delta``: raise the blade by ``d(s) + delta``, so that at the
probe station it sits ``delta`` above the stock's own running surface.

If ``sigma(delta)`` collapses onto one curve across stations, an estimator can use a single law with
``u = d - z``.  If it shifts, the law is a two-dimensional operator and the inversion has to carry it.

Nothing is fitted here; this is a measurement across mileage at one speed.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.solver import SimulationFailure  # noqa: E402
from velch.vehicle_solver import VehicleDynamics, _seat  # noqa: E402

import s117_split_law as LAW  # noqa: E402

CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s118"
STATIONS_M = (52.0, 54.0, 56.0, 58.0, 60.0, 62.0)
DELTAS_UM = (250.0, 100.0, 50.0, 0.0, -50.0, -100.0, -200.0)
AXLE_OFFSET_M = 10.0
RAIL = "axle1_right"


def _crown(series, station_m: float) -> float:
    return float(np.max(series.sample(station_m, 1.0).profile.z_m))


def _gap_at(base: dict, station_m: float) -> float:
    """stock crown minus blade crown at ``station_m``, both from the case's own series."""
    case = load_vehicle_case(CASE)
    rail = next(item for item in case.rails if item.id == RAIL)
    bodies = {body.id: body for body in rail.contact_bodies}
    return _crown(bodies["stock"].series, station_m) - _crown(bodies["blade"].series, station_m)


def main() -> int:
    base = json.loads(CASE.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    print(f"{'station (m)':>11s} {'design gap (um)':>16s}", end="")
    for delta in DELTAS_UM:
        print(f" {delta:+6.0f}", end="")
    print("   half width at delta=0 (mm)")

    for station in STATIONS_M:
        gap = _gap_at(base, station)
        line = {}
        for delta in DELTAS_UM:
            # Positive delta = blade above flush; the case's z_offset is a *raise* measured from the design
            # position, so raise it by the whole design gap plus the requested height above flush.
            raise_m = gap + delta * 1e-6
            shifted = LAW._shifted_blade(base, raise_m)
            shifted["run"]["x_start_m"] = station - AXLE_OFFSET_M
            if "seat_x_start_m" in shifted["run"]:
                shifted["run"]["seat_x_start_m"] = station - AXLE_OFFSET_M
            try:
                result = LAW._split_at_the_front_axle(shifted)
            except SimulationFailure as failure:
                # A blade lifted far above the stock leaves the stock with nothing to carry, and the vertical
                # seat has no equilibrium to find.  That is a real boundary of the method, recorded as a failed
                # cell rather than hidden by quietly narrowing the grid.
                result = {"sigma": float("nan"), "stock_n": float("nan"),
                          "blade_n": float("nan"), "total_n": float("nan"),
                          "half_width_m": float("nan"), "lever_y_m": float("nan"),
                          "stock_active": False, "blade_active": False,
                          "residual_n": float("nan"), "failed": str(failure)[:80]}
            line[delta] = result
            rows.append({"station_m": station, "design_gap_m": gap, "delta_um": delta,
                         **result})
        print(f"{station:11.1f} {gap * 1e6:16.1f}", end="")
        for delta in DELTAS_UM:
            print(f" {line[delta]['sigma']:6.3f}", end="")
        width = line[0.0]["half_width_m"]
        print(f"   {width * 1e3:6.3f}")

    # Where does each station's law cross one half?  That is the station-dependent transfer height.
    print()
    print(f"{'station (m)':>11s} {'delta at sigma=0.5 (um)':>24s} {'delta at sigma=0.9 (um)':>24s}")
    half_rows = []
    for station in STATIONS_M:
        series = [(delta, next(row for row in rows
                               if row["station_m"] == station and row["delta_um"] == delta))
                  for delta in sorted(DELTAS_UM)]
        def crossing(target: float) -> float:
            for (low_d, low), (high_d, high) in zip(series, series[1:]):
                if low["sigma"] < target <= high["sigma"] + 1e-12:
                    span = high["sigma"] - low["sigma"]
                    if span <= 1e-9:
                        return float("nan")
                    t = (target - low["sigma"]) / span
                    return low_d + t * (high_d - low_d)
            return float("nan")
        half = crossing(0.5)
        nine = crossing(0.9)
        half_rows.append({"station_m": station, "delta_half_um": half, "delta_ninety_um": nine})
        print(f"{station:11.1f} {half:24.1f} {nine:24.1f}")

    halves = [row["delta_half_um"] for row in half_rows if np.isfinite(row["delta_half_um"])]
    spread = (max(halves) - min(halves)) if halves else float("nan")
    print()
    print(f"stations where sigma reaches 0.5: {len(halves)}/{len(half_rows)}   "
          f"spread of the half-load height {spread:.1f} um")
    print("VERDICT: " + ("the split law collapses onto one curve in height-above-flush coordinates"
                         if np.isfinite(spread) and spread <= 100.0 else
                         "the split law moves with mileage -- it is a two-dimensional operator"))
    (OUT / "split_law_vs_station.json").write_text(json.dumps(
        {"rail": RAIL, "stations_m": list(STATIONS_M), "deltas_um": list(DELTAS_UM),
         "rows": rows, "crossings": half_rows, "half_height_spread_um": spread}, indent=1) + chr(10),
        encoding="utf-8")
    print(f"report -> {OUT / 'split_law_vs_station.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
