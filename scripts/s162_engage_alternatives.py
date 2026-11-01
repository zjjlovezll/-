"""Ask the two remaining candidates for the 60 km/h offset: the rail's own lateral motion, and the threshold.

Round 309 imposed the archived 3.096 mm wheelset displacement and found it worth only 8.6 mm of station against
the 145 mm that has to be explained.  Two candidates survive, and both are readable from the archives that
already exist:

* **the compliant rail moves too** -- these runs use ``local_compliant`` track, so each rail carries its own
  lateral coordinate.  A rail that shifts inward changes the *relative* lateral registration exactly like a
  wheelset that shifts outward, and round 309 measured that exchange rate (share moves 10.15 per metre of
  displacement);
* **the 5 % threshold is a share, not a force** -- ``engage`` fires when the blade carries 5 % of the *instant's*
  total.  The total sags during the transient, so the same blade force crosses 5 % earlier.  An absolute
  threshold (5 % of the static share, 3.007 kN) cannot be fooled that way.

Registered before measuring:

* **H11** -- the rail lateral difference between 60 and 80 km/h at 58.150 m, converted at 10.15 per metre and
  120 pp per metre of station, accounts for **at least 0.05 m** of the 0.145 m;
* **H12** -- under the absolute threshold the 60 km/h crossing moves to **58.10 m or later**, i.e. to within
  0.05 m of the static reference 58.145 m.

Falsifiers: H11 fails if the converted station is under 0.05 m; H12 fails if it stays before 58.10 m.  Both
failing sends the search to a new simulation (the 60 km/h lateral starting state), which is not this round.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics  # noqa: E402

RUNS_DIR = ROOT.parent / "scratch" / "runs"
CASE = ROOT.parent / "scratch" / "s146" / "one_set_x46.json"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "engage_alternatives.json"

SPEEDS_KMH = (60.0, 80.0, 100.0)
STATION_M = 58.150
AXLE_OFFSET_M = 10.0
RAIL_ID = "axle1_right"
BODY_ID = "blade"

#: Share slope at this station, measured in round 305's 0.05 m grid (120 pp per metre).
SHARE_SLOPE_PER_M = 120.0
#: Share change per metre of lateral displacement, measured in round 309.
SHARE_PER_DISPLACEMENT = 10.15
#: 5 % of the static share at 481 078.5 N / 8 = 60 134.8 N.
STATIC_SHARE_N = 60_134.8
SHARE_TARGET = 0.05
ABSOLUTE_THRESHOLD_N = SHARE_TARGET * STATIC_SHARE_N
#: The offset under investigation, from round 304's measured crossings.
REQUIRED_OFFSET_M = 0.145
STATIC_REFERENCE_M = 58.145

H11_FLOOR_M = 0.05
H12_CEILING_M = 58.10


def _run_dir(speed_kmh: float) -> pathlib.Path:
    pattern = f"one_set_x46-{int(round(speed_kmh)):03d}.00kmh-*"
    found = sorted(RUNS_DIR.glob(pattern))
    if not found:
        raise SystemExit(f"no null-route archive for {speed_kmh} km/h (pattern {pattern})")
    # Several campaigns archived the same speed at different durations; the longest window is the one that
    # reaches the crossing, and picking the first alphabetically silently handed back a 0.02 s slice.
    def duration(path: pathlib.Path) -> float:
        meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
        return float(meta["times_s"][-1]) if "times_s" in meta else float(meta["duration_s"])

    return max(found, key=duration)


def _rail_lateral_index() -> tuple[int, int, list[str]]:
    """Position of ``axle1_right``'s lateral coordinate in the state vector, and the track's names."""

    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    names = list(dynamics.track.state_names)
    rail_ids = [rail.id for rail in dynamics.track.rails]
    column = 2 * rail_ids.index(RAIL_ID)
    offset = dynamics.track.offset
    dynamics.close()
    return offset + column, column, names


def load(speed_kmh: float) -> dict:
    directory = _run_dir(speed_kmh)
    series = np.load(directory / "series.npz")
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    times = series["times"]
    speed = float(meta["speed_m_s"])
    front = float(meta["x_start_m"]) + AXLE_OFFSET_M + speed * times
    index, column, names = _rail_lateral_index()
    lateral = series["positions"][:, index]
    labels = list(meta["body_labels"])
    blade_column = [i for i, label in enumerate(labels) if label.endswith("/" + BODY_ID)]
    rails = list(meta["rail_ids"])
    rail_force = series["normal_force_n"][:, rails.index(RAIL_ID)]
    body_force = series["body_normal_force_n"]
    return {
        "run_id": directory.name,
        "speed_kmh": speed_kmh,
        "times": times,
        "front_m": front,
        "rail_lateral_m": lateral,
        "rail_lateral_name": names[column],
        "blade_n": body_force[:, blade_column[0]] if blade_column else np.zeros_like(times),
        "total_n": rail_force,
    }


def station_value(station: np.ndarray, values: np.ndarray, target: float) -> float:
    return float(np.interp(target, station, values))


def drift(station: np.ndarray, values: np.ndarray, low: float, high: float) -> float:
    mask = (station >= low) & (station <= high)
    if mask.sum() < 3:
        return float("nan")
    return float(np.polyfit(station[mask], values[mask], 1)[0])


def first_crossing(station: np.ndarray, signal: np.ndarray, threshold: float) -> float | None:
    for i in range(1, len(signal)):
        if signal[i] >= threshold >= signal[i - 1]:
            span = signal[i] - signal[i - 1]
            if span <= 0.0:
                return float(station[i])
            weight = (threshold - signal[i - 1]) / span
            return float(station[i - 1] + weight * (station[i] - station[i - 1]))
    return None


def measure() -> dict:
    rows = {}
    for speed in SPEEDS_KMH:
        run = load(speed)
        station = run["front_m"]
        share = run["blade_n"] / np.where(run["total_n"] > 0.0, run["total_n"], np.nan)
        rows[f"{speed:g}"] = {
            "run_id": run["run_id"],
            "rail_lateral_mm_at_station": 1e3 * station_value(station, run["rail_lateral_m"], STATION_M),
            "rail_lateral_drift_mm_per_m": 1e3 * drift(station, run["rail_lateral_m"], STATION_M - 0.6, STATION_M + 0.6),
            "blade_kn_at_station": 1e-3 * station_value(station, run["blade_n"], STATION_M),
            "total_kn_at_station": 1e-3 * station_value(station, run["total_n"], STATION_M),
            "share_at_station": station_value(station, share, STATION_M),
            "engage_share_m": first_crossing(station, share, SHARE_TARGET),
            "engage_absolute_m": first_crossing(station, run["blade_n"], ABSOLUTE_THRESHOLD_N),
            "station_span_m": [float(station.min()), float(station.max())],
        }
    return {
        "rows": rows,
        "constants": {
            "station_m": STATION_M,
            "rail_id": RAIL_ID,
            "share_slope_per_m": SHARE_SLOPE_PER_M,
            "share_per_displacement": SHARE_PER_DISPLACEMENT,
            "absolute_threshold_n": ABSOLUTE_THRESHOLD_N,
            "static_share_n": STATIC_SHARE_N,
            "required_offset_m": REQUIRED_OFFSET_M,
            "static_reference_m": STATIC_REFERENCE_M,
            "h11_floor_m": H11_FLOOR_M,
            "h12_ceiling_m": H12_CEILING_M,
        },
    }


def verdict(report: dict) -> dict:
    rows = report["rows"]
    sixty, eighty, hundred = rows["60"], rows["80"], rows["100"]
    rail_delta_mm = sixty["rail_lateral_mm_at_station"] - eighty["rail_lateral_mm_at_station"]
    share_delta = SHARE_PER_DISPLACEMENT * 1e-3 * rail_delta_mm
    equivalent_m = abs(share_delta) / SHARE_SLOPE_PER_M
    absolute = sixty["engage_absolute_m"]
    return {
        "rail_lateral_delta_mm": rail_delta_mm,
        "share_delta_from_rail": share_delta,
        "station_equivalent_m": equivalent_m,
        "h11_rail_takes_the_offset": bool(equivalent_m >= H11_FLOOR_M),
        "engage_share_60_m": sixty["engage_share_m"],
        "engage_absolute_60_m": absolute,
        "absolute_gain_m": None if absolute is None else absolute - float(sixty["engage_share_m"]),
        "h12_absolute_threshold_closes_it": bool(absolute is not None and absolute >= H12_CEILING_M),
        "engage_share_spread_m": max(r["engage_share_m"] for r in rows.values())
        - min(r["engage_share_m"] for r in rows.values()),
        "engage_absolute_spread_m": max(r["engage_absolute_m"] for r in rows.values())
        - min(r["engage_absolute_m"] for r in rows.values()),
        "hundred_note": "100 km/h is read out for context only; it is not part of either hypothesis",
        "purpose": "ask whether the rail's own motion or the share threshold carries the 60 km/h offset",
        "hundred_engage_absolute_m": hundred["engage_absolute_m"],
    }


def main() -> int:
    report = measure()
    report["verdict"] = verdict(report)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"{'speed':>7} {'rail y mm':>10} {'drift mm/m':>11} {'blade kN':>9} {'total kN':>9} "
          f"{'share':>8} {'engage %':>9} {'engage kN':>9}")
    for speed in SPEEDS_KMH:
        row = report["rows"][f"{speed:g}"]
        print(f"{speed:7.1f} {row['rail_lateral_mm_at_station']:10.3f} {row['rail_lateral_drift_mm_per_m']:11.4f} "
              f"{row['blade_kn_at_station']:9.3f} {row['total_kn_at_station']:9.3f} "
              f"{100.0 * row['share_at_station']:7.2f}% "
              f"{row['engage_share_m']:9.3f} {row['engage_absolute_m']:9.3f}")
    print()
    v = report["verdict"]
    print(f"rail lateral 60-80     {v['rail_lateral_delta_mm']:+.4f} mm")
    print(f"share it buys          {v['share_delta_from_rail']:+.4f} pp   station equivalent {v['station_equivalent_m']:.4f} m")
    print(f"H11 rail takes it      {v['h11_rail_takes_the_offset']}  (floor {H11_FLOOR_M} m of the {REQUIRED_OFFSET_M} m)")
    print(f"share  engage 60       {v['engage_share_60_m']:.3f} m")
    print(f"absolute engage 60     {v['engage_absolute_60_m']:.3f} m  gain {v['absolute_gain_m']:+.3f} m")
    print(f"H12 threshold closes   {v['h12_absolute_threshold_closes_it']}  (ceiling {H12_CEILING_M} m)")
    print(f"spread share {v['engage_share_spread_m']:.3f} m   absolute {v['engage_absolute_spread_m']:.3f} m")
    print(f"report -> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
