"""Where was the wheel, laterally, when the blade took its 5 % share?

Round 307 showed that the two-spring split answers the same question at every speed: seated at fourteen
stations it returns the same effective gap and the same share to 1e-12, so its 5 % reference is pinned at
58.145 m.  The archive says the measured engage(5 %) station is 58.000 m at 60 km/h and 58.156 / 58.153 m at
80 / 100 km/h.  So the split is static, the measurement is not, and the difference has to be carried by
some quantity the seat does not model: the lateral position of the wheel.

That is a claim about a number, so it is written down before the number is read:

    H8: at the station where the front axle passes 58.150 m, the front wheelset's lateral coordinate in the
        60 km/h run exceeds the 80 km/h run by at least 0.20 mm, and it is displaced towards the blade
        (larger y -- at 58.2 m the blade's contact sits at 753.355 mm against the stock's 751.752 mm), so
        the blade is deeper and its share reaches 5 % earlier at 60 km/h.

    falsifier: |dy| < 0.20 mm, or dy < 0.  Either outcome means the lateral registration does not carry the
    0.145 m, and the offset stays unexplained rather than being attributed by narrative.

The 0.20 mm is not a tolerance on an error; it is the smallest displacement that is unambiguously larger
than the 0.05 mm station grid used to report the crossing (four grid cells), and it is stated here so that a
sub-grid agreement cannot be read as a mechanism.

Purpose is measurement.  Nothing is fitted, no gate is judged, and the three runs are read exactly as the
solver wrote them.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics  # noqa: E402

RUNS_DIR = ROOT.parent / "scratch" / "runs"
CASE = ROOT.parent / "scratch" / "s146" / "one_set_x46.json"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "engage_registration.json"
RUN_IDS = {
    60.0: "one_set_x46-060.00kmh-0.5400s-500us-83e727fc",
    80.0: "one_set_x46-080.00kmh-0.1000s-500us-83e727fc",
    100.0: "one_set_x46-100.00kmh-0.3300s-500us-83e727fc",
}
STATIONS_M = (57.4, 58.0, 58.15, 58.5, 59.0, 59.2)
AXLE_OFFSET_M = 10.0          # front-axle station = x_start + this + distance travelled
TARGET_STATION_M = 58.150
WHEELSETS = ("wheelset1", "wheelset2", "wheelset3", "wheelset4")
ENGAGE_5PCT_M = {60.0: 58.000, 80.0: 58.156, 100.0: 58.153}
MIN_DISPLACEMENT_M = 0.20e-3  # H8, declared above before any run is read


def lateral_indices() -> dict:
    """State index of the lateral coordinate of each wheelset, read from the topology itself."""
    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    found = {}
    for name in WHEELSETS:
        found[name] = int(dynamics.topology.require(name, "y"))
    return found


def displacement(run_id: str, index: int, stations) -> tuple[dict, dict]:
    """Front wheelset lateral position against station, from one archived run."""
    run = RUNS_DIR / run_id
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    series = np.load(run / "series.npz")
    times = np.asarray(series["times"], dtype=float)
    lateral = np.asarray(series["positions"], dtype=float)[:, index]
    station = meta["x_start_m"] + AXLE_OFFSET_M + meta["speed_m_s"] * times
    values = {round(float(s), 3): float(np.interp(s, station, lateral)) for s in stations}
    # Drift of the lateral coordinate with distance travelled, over the same window.
    inside = (station >= stations[0]) & (station <= stations[-1])
    slope = float(np.polyfit(station[inside], lateral[inside], 1)[0]) if inside.sum() > 2 else float("nan")
    info = {"run_id": run_id, "speed_kmh": meta["speed_kmh"], "frames": int(times.size),
            "wall_s": meta.get("wall_s"), "drift_m_per_m": slope}
    return values, info


def main(argv: list | None = None) -> int:
    indices = lateral_indices()
    rows, info = {}, {}
    for speed, run_id in RUN_IDS.items():
        values, meta = displacement(run_id, indices["wheelset1"], STATIONS_M)
        rows[speed] = values
        info[speed] = meta

    target = rows[80.0][TARGET_STATION_M]
    deltas = {speed: rows[speed][TARGET_STATION_M] - target for speed in (60.0, 100.0)}
    delta_60 = deltas[60.0]

    print("front wheelset lateral coordinate (mm) against front-axle station")
    header = "  station  " + "  ".join(f"{speed:>6.0f} km/h" for speed in sorted(rows))
    print(header)
    for station in STATIONS_M:
        print(f"  {station:7.3f}  " + "  ".join(f"{1e3 * rows[speed][station]:12.4f}" for speed in sorted(rows)))

    print()
    print("drift of the lateral coordinate over the window (mm per metre travelled)")
    for speed in sorted(info):
        print(f"  {speed:6.0f} km/h  {1e3 * info[speed]['drift_m_per_m']:+.5f} mm/m   ({info[speed]['run_id']})")

    print()
    print(f"reference station {TARGET_STATION_M:.3f} m, 80 km/h value {1e3 * target:+.4f} mm")
    print(f"  60 km/h minus 80 km/h  {1e3 * delta_60:+.4f} mm   (H8 needs >= {1e3 * MIN_DISPLACEMENT_M:+.3f} mm)")
    print(f" 100 km/h minus 80 km/h  {1e3 * deltas[100.0]:+.4f} mm")
    print(f"  measured engage(5 %)   " + "  ".join(f"{speed:g}: {ENGAGE_5PCT_M[speed]:.3f} m" for speed in sorted(ENGAGE_5PCT_M)))

    passes = delta_60 >= MIN_DISPLACEMENT_M
    print()
    print(f"H8 (the 60 km/h offset is a lateral registration towards the blade): "
          f"{'CONFIRMED' if passes else 'REFUTED'}")
    if not passes:
        print("  the 0.145 m offset stays unexplained; the registration is not its carrier")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "constants": {"stations_m": list(STATIONS_M), "target_station_m": TARGET_STATION_M,
                      "min_displacement_m": MIN_DISPLACEMENT_M, "axle_offset_m": AXLE_OFFSET_M,
                      "engage_5pct_m": {str(k): v for k, v in ENGAGE_5PCT_M.items()},
                      "lateral_indices": indices},
        "rows": {str(speed): {f"{k:.3f}": v for k, v in values.items()} for speed, values in rows.items()},
        "runs": {str(speed): meta for speed, meta in info.items()},
        "deltas_m": {"60_vs_80": delta_60, "100_vs_80": deltas[100.0]},
        "H8_lateral_registration": bool(passes),
    }, indent=1, sort_keys=True), encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0 if passes else 1


if __name__ == "__main__":
    raise SystemExit(main())
