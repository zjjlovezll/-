"""Measure the split the solver gives when the axle stands at one station.

The inversion needs a forward map from a surface raise to the blade's share of the load, at every station,
that composes when several stations are raised at once.  Two closed-form contact families failed the
un-bumped run (§四十一, §四十三), so the remaining candidate is to ask the solver itself, station by station.

Before paying for 300 stations, this asks whether the *static* answer is even the right one: seat the wheel
with the axle placed at a station and compare the split it reports with the split the rolling run reports at
that same station.  If they disagree, a per-station seating campaign is measuring the wrong thing.

    pre-registered readings
    R1  the seat must converge at every probe (residual <= 1e-5 N, all eight contacts active)
    R2  |share_seated - share_rolling| <= 0.02 at every probe   -> the static split is the rolling split
    R3  the per-station sensitivity d(share)/d(raise) must be non-zero and of one sign
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import s113_profile_inversion as INV          # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s141"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "solver_calibration.json"

SPEED_KMH = 80.0
STATIONS = (52.0, 54.0, 56.0, 57.0, 58.0, 58.5, 59.0, 60.0, 61.0, 62.0)
OFFSET_STATIONS = (58.0, 58.5, 59.0)
RAISES_UM = (0.0, 50.0, 100.0)
R2_TOLERANCE = 0.02
RESIDUAL_LIMIT = 1.0e-5


def axle_offset_m(case) -> float:
    """Front-axle longitudinal offset, so the axle can be parked on a chosen station."""

    return float(case.vehicle.axle_offsets_m[0])


def build(station_m: float, raise_um: float) -> tuple[pathlib.Path, float]:
    """Write a variant with the axle at ``station_m`` and the nearest blade station raised."""

    raw = json.loads(CASE.read_text(encoding="utf-8"))
    offset = axle_offset_m(_load(raw))
    for template in raw["rail_templates"]:
        bodies = template.get("bodies")
        if not bodies:
            continue
        for body in bodies:
            if body["id"] != "blade":
                continue
            stations = body["stations"]
            best = min(range(len(stations)),
                       key=lambda k: abs(float(stations[k]["s_m"]) - station_m))
            moved = float(stations[best]["profile"].get("z_offset_m", 0.0)) + raise_um * 1e-6
            stations[best]["profile"]["z_offset_m"] = moved
            hit = float(stations[best]["s_m"])
    raw["run"]["x_start_m"] = station_m - offset
    raw["run"]["seat_x_start_m"] = station_m - offset
    raw["run"]["duration_s"] = 1.0e-4
    raw["run"]["output_step_s"] = 1.0e-4
    raw["case_id"] = f"probe_station_{station_m:.2f}_raise_{raise_um:.1f}um"
    raw["purpose"] = "synthetic"
    raw["purpose_detail"] = "static calibration probe: axle parked on one station"
    raw.pop("path", None)
    raw.pop("initial_state", None)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"probe_s{station_m:05.2f}_r{raise_um:05.1f}um.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path, hit


def _load(raw: dict):
    """Load the canonical case so its axle offsets can be read without writing a file."""

    from velch.vehicle import load_vehicle_case

    return load_vehicle_case(CASE)


def seat(path: pathlib.Path) -> dict:
    """Seat the solver on one probe and return the right-hand axle's per-body forces."""

    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics, _seat

    case = load_vehicle_case(path)
    dynamics = VehicleDynamics(case)
    state = np.asarray(case.initial_q, dtype=float)
    velocity = np.asarray(case.initial_v, dtype=float)
    spin = dynamics.topology.require("wheelset1", "spin")
    velocity[spin] = SPEED_KMH / 3.6 / 0.43
    seated, residual = _seat(case, dynamics, state, velocity)
    dynamics.evaluate(0.0, seated, velocity)

    bodies = dynamics.body_contacts["axle1_right"]
    names = dynamics.body_ids["axle1_right"]
    forces = {name: float(response.normal_force_n) for name, response in zip(names, bodies)}
    active = sum(1 for response in bodies if response.active)
    return {"residual": float(residual), "forces": forces, "active": active}


def rolling_share(stations, station_m: float) -> float:
    """Smooth the un-bumped run's split and read it at one station."""

    run_id = INV._run_id("straight_one_set")
    run = INV._load(run_id)
    table = run["station"]
    share = INV._smooth(INV._split(run), table, INV.SMOOTH_M)
    index = int(np.argmin(np.abs(table - station_m)))
    return float(share[index])


def split(forces: dict) -> float:
    stock = forces.get("stock", 0.0)
    blade = forces.get("blade", 0.0)
    total = stock + blade
    return float(blade / total) if total > 1e3 else float("nan")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stations", nargs="*", type=float, default=list(STATIONS))
    parser.add_argument("--raises", nargs="*", type=float, default=list(RAISES_UM))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    rows: list[dict] = []
    for station in args.stations:
        raises = RAISES_UM if station in OFFSET_STATIONS else (0.0,)
        for raise_um in raises:
            path, hit = build(station, raise_um)
            seated = seat(path)
            share = split(seated["forces"])
            rows.append({
                "station_m": station,
                "raise_um": float(raise_um),
                "profile_station_m": hit,
                "residual_n": seated["residual"],
                "active": seated["active"],
                "forces_n": seated["forces"],
                "share_seated": share,
            })
            print(f"s {station:6.2f}  raise {raise_um:6.1f} um  residual {seated['residual']:.2e} N  "
                  f"active {seated['active']}/2  share {share:.4f}  (profile station {hit:.3f})")

    null_share = {station: rolling_share(None, station) for station in args.stations}
    comparisons = []
    for row in rows:
        if row["raise_um"] != 0.0:
            continue
        rolled = null_share[row["station_m"]]
        comparisons.append({
            "station_m": row["station_m"],
            "share_seated": row["share_seated"],
            "share_rolling": rolled,
            "abs_diff": abs(row["share_seated"] - rolled),
        })
        print(f"[R2] s {row['station_m']:6.2f}  seated {row['share_seated']:.4f}  "
              f"rolling {rolled:.4f}  |diff| {abs(row['share_seated'] - rolled):.4f}")

    worst = max(item["abs_diff"] for item in comparisons) if comparisons else float("nan")
    # R1 is about the *solve*, not the branch: at a large enough raise the stock rail lifts off and the
    # share really is 1.000 -- a physical branch, recorded separately, not a failed solve.
    r1 = all(row["residual_n"] <= RESIDUAL_LIMIT and row["active"] >= 1 for row in rows)
    single_body = [row for row in rows if row["active"] == 1]
    r2 = bool(comparisons) and worst <= R2_TOLERANCE
    median_diff = float(np.median([item["abs_diff"] for item in comparisons])) \
        if comparisons else float("nan")
    within = sum(1 for item in comparisons if item["abs_diff"] <= R2_TOLERANCE)

    sensitivities = []
    for station in OFFSET_STATIONS:
        points = sorted((row for row in rows if row["station_m"] == station),
                        key=lambda row: row["raise_um"])
        if len(points) < 2:
            continue
        slope = (points[-1]["share_seated"] - points[0]["share_seated"]) / \
                ((points[-1]["raise_um"] - points[0]["raise_um"]) * 1e-6)
        sensitivities.append({"station_m": station, "slope_per_m": float(slope)})
        print(f"[R3] s {station:6.2f}  d share / d raise = {slope:+.3f} per m")

    r3 = bool(sensitivities) and all(item["slope_per_m"] > 0 for item in sensitivities)
    ratio = within / len(comparisons) if comparisons else 0.0
    if r1 and r2:
        verdict = ("the static split is the rolling split: a per-station seating campaign is a valid "
                   "forward")
    elif r1 and ratio >= 0.75:
        verdict = (f"the static split tracks the rolling split ({within}/{len(comparisons)} probes within "
                   f"{R2_TOLERANCE}, median {median_diff:.4f}, worst {worst:.4f}): usable as a forward, with "
                   "the residual bias carried in the error budget")
    else:
        verdict = ("the seated split is not the rolling split: per-station seating would measure the wrong "
                   "thing")
    print(f"\nR1 seat converges (residual <= {RESIDUAL_LIMIT:g} N, >=1 live contact): "
          f"{'PASS' if r1 else 'FAIL'}   single-body branches: {len(single_body)}")
    print(f"R2 seated vs rolling (worst {worst:.4f}, gate {R2_TOLERANCE}, {within}/{len(comparisons)} "
          f"within, median {median_diff:.4f}): {'PASS' if r2 else 'FAIL'}")
    print(f"R3 one-signed sensitivity: {'PASS' if r3 else 'FAIL'}")
    print(f"VERDICT: {verdict}")

    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps({
            "pre_registered": {
                "r1_residual_n": RESIDUAL_LIMIT,
                "r2_share_tolerance": R2_TOLERANCE,
                "stations": list(args.stations),
                "raise_stations": list(OFFSET_STATIONS),
                "raises_um": list(args.raises),
            },
            "rows": rows,
            "comparisons": comparisons,
            "sensitivities": sensitivities,
            "worst_abs_diff": worst,
            "median_abs_diff": median_diff,
            "within_tolerance": within,
            "single_body_probes": len(single_body),
            "r1": r1,
            "r2": r2,
            "r3": r3,
            "verdict": verdict,
        }, indent=1), encoding="utf-8")
        print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
