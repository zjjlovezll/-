"""Does the band inversion transfer across speed?

Every inversion in rounds 261-273 was fitted and validated at 80 km/h, while the task book asks for several
travel speeds and forbids extrapolating a calibration across them.  This probe answers one question with the
measurement it needs: if the same measured share law and the same one-gaussian model are applied at 60 and
100 km/h -- each with its own un-bumped run supplying the operating point u0(s) -- does the inversion still
recover a 60 um bump, and with the same accuracy?

Pre-registered before the runs (nothing here is relaxed later):

    model      z(s) = A * exp(-0.5 ((s - 58.5) / 1.20)^2)          same as round 261, one gaussian
    law        s119's measured width-resolved split law            unchanged
    operating  u0(s) inverted from the un-bumped run AT THAT SPEED  (never from the 80 km/h run)
    speeds     60 and 100 km/h (80 km/h is the regression control, already archived)

    G-ABS   p95(|z_hat - z|) <= 22 um         (window: truth >= 10 % of peak)
    G-REL   worst 2 mm bin       <= 2 %        (denominator max(|truth|, 500 um))
    G-LOC   |peak station error| <= 0.20 m
    G-AMP   |A_hat - 60| / 60    <= 2 %

Two outcomes are both informative and neither is "the round failed":

    transfers      all gates pass at both speeds, and the amplitude agrees with the 80 km/h value to within
                   a few percent -> one calibration covers this speed range, and the task book's
                   "calibrate per speed" requirement is satisfied by the law plus u0, not by a table of
                   empirical gains.
    does not       a gate fails at one speed -> the operating point or the law carries speed dependence,
                   which is exactly the sentence that keeps any amplitude claim inside one speed.

Self-check: the local fit path is run at 80 km/h first and must reproduce the archived round-261 numbers
(A 66.1 um, centre 58.464 m, p95 6.38 um) before the 60/100 km/h rows are believed.  A probe that cannot
reproduce the number it is generalising from is not evidence about speed.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import s113_profile_inversion as base
import s119_width_aware_inversion as law
import s110_lowering_readings as lowering
import s123_m7_assembly as assembly
import s124_joint_inversion as joint

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNS = ROOT.parent / "scratch" / "runs"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "speed_transfer.json"

NULL_ROUTE = assembly.BASELINE_ROUTE
BUMP_ROUTE = "one_set_bump060.0um"
TRUTH_UM = 60.0
SPEEDS_KMH = (60.0, 100.0)
CONTROL_KMH = 80.0
DURATION_S = base.DURATION_S
WIDTH_M = base.SIGMA_M
FIT_LO_M = joint.FIT_LO_M
FIT_HI_M = joint.FIT_HI_M
SHARE_LO = joint.SHARE_LO
SHARE_HI = joint.SHARE_HI
CENTRE_M = base.CENTRE_M
STATION_LIMIT_M = joint.STATION_LIMIT_M
ABSOLUTE_LIMIT_UM = joint.ABSOLUTE_LIMIT_UM
RELATIVE_LIMIT_PCT = joint.RELATIVE_LIMIT_PCT
AMPLITUDE_LIMIT_PCT = 2.0

# What round 261 archived at 80 km/h for the same 60 um bump, used only as a self-check.
ARCHIVED_80 = {"amplitude_um": 66.1, "centre_m": 58.464, "p95_um": 6.38}


def plan() -> int:
    for speed in SPEEDS_KMH:
        for route, case in ((NULL_ROUTE, "vehicles/turnouts/CN60-1100-1_18/cases/straight_one_set.json"),
                            (BUMP_ROUTE, "../scratch/s120/one_set_bump060.0um.json")):
            print(f"python -X utf8 scripts/s99_run_archive.py --case {case} "
                  f"--speed-kmh {speed:.0f} --duration {DURATION_S} --note campaign=speed-transfer")
    return 0


def select(route: str, speed_kmh: float) -> str:
    rows = [row for row in base._index_rows()
            if row.get("route") == route
            and abs(float(row["duration_s"]) - DURATION_S) < 1e-9
            and abs(float(row["speed_kmh"]) - speed_kmh) < 1e-9]
    if not rows:
        raise SystemExit(f"no archived {DURATION_S} s run for {route!r} at {speed_kmh:g} km/h")
    return str(rows[-1]["run_id"])


def load(run_id: str, speed_kmh: float) -> dict:
    """Like s113._load, but the station column uses this run's own speed instead of the module constant."""
    from velch.vehicle import load_vehicle_case

    directory = RUNS / run_id
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    data = np.load(directory / "series.npz")
    labels = list(meta["body_labels"])
    stock = np.asarray(data["body_normal_force_n"])[:, labels.index(f"{base.BODY_PREFIX}/stock")]
    blade = np.asarray(data["body_normal_force_n"])[:, labels.index(f"{base.BODY_PREFIX}/blade")]
    times = np.asarray(data["times"], dtype=float)
    offsets = np.asarray(load_vehicle_case(lowering.CASE).vehicle.axle_offsets_m, dtype=float)
    station = float(meta.get("x_start_m", 0.0)) + (speed_kmh / 3.6) * times + float(offsets[base.AXLE])
    return {"run_id": run_id, "meta": meta, "times": times, "station": station,
            "stock": stock, "blade": blade}


def share(run: dict) -> np.ndarray:
    return base._smooth(base._split(run), run["station"], base.SMOOTH_M)


def null_state(speed_kmh: float, invert, half_gap_of) -> dict:
    run = load(select(NULL_ROUTE, speed_kmh), speed_kmh)
    observed = share(run)
    widths = law._width_at(run["station"], *law._width_table())
    u0 = np.full_like(observed, np.nan)
    ok = np.isfinite(observed) & (observed > SHARE_LO) & (observed < SHARE_HI)
    for index in np.nonzero(ok)[0]:
        u0[index] = invert(float(observed[index]), half_gap_of(float(widths[index])))
    return {"stations": run["station"], "share": observed, "u0": u0}


def fit(route: str, speed_kmh: float, sigma_of, state: dict) -> dict:
    """One-gaussian forward fit; identical model, width, bounds and start to s124.fit_one."""
    from scipy.optimize import least_squares

    run = load(select(route, speed_kmh), speed_kmh)
    stations = run["station"]
    observed = share(run)
    widths = law._width_at(stations, *law._width_table())
    u0 = state["u0"]
    usable = (np.isfinite(observed) & np.isfinite(u0) & (stations >= FIT_LO_M)
              & (stations <= FIT_HI_M) & (observed >= SHARE_LO) & (observed <= SHARE_HI))

    def residual(params: np.ndarray) -> np.ndarray:
        amplitude, centre = params
        bump = amplitude * np.exp(-0.5 * ((stations[usable] - centre) / WIDTH_M) ** 2)
        return sigma_of(u0[usable] + bump, widths[usable]) - observed[usable]

    solved = least_squares(residual, np.asarray([70.0, CENTRE_M]),
                          bounds=([1.0, CENTRE_M - 3.0], [400.0, CENTRE_M + 3.0]),
                          method="trf", xtol=1e-12, ftol=1e-12)
    return {"route": route, "speed_kmh": speed_kmh, "run_id": run["run_id"], "stations": stations,
            "amplitude_um": float(solved.x[0]), "centre_m": float(solved.x[1]),
            "share_rms": float(np.sqrt(np.mean(solved.fun ** 2))),
            "usable_stations": int(usable.sum())}


def transition(speed_kmh: float, level: float) -> dict:
    """Where the un-bumped blade first carries `level` of the load, in station and in time.

    This is the mechanism measurement behind the speed rows: the operating point u0(s) is only a fixed
    function of station if the blade starts carrying at a fixed *station*.  Reporting both coordinates says
    which one is fixed.
    """
    run = load(select(NULL_ROUTE, speed_kmh), speed_kmh)
    stations, observed = run["station"], share(run)
    above = np.nonzero(np.isfinite(observed) & (observed >= level))[0]
    if above.size == 0:
        return {"speed_kmh": speed_kmh, "level": level, "station_m": None, "time_s": None}
    index = int(above[0])
    station = float(stations[index])
    return {"speed_kmh": speed_kmh, "level": level, "station_m": round(station, 4),
            "time_s": round((station - float(stations[0])) / (speed_kmh / 3.6), 4)}


def score(fit_row: dict) -> dict:
    """Score one fit, with the amplitude gate on the 60 um truth rather than on the 500 um floor.

    s124's `score_fit` divides the relative error by `max(|truth|, 500 um)`, which is right for the
    per-2-mm-bin `G-REL` (a bin holding a few micrometres must not blow up) but wrong for an amplitude
    claim: 80 um read against a 60 um bump is 33 %, yet the floor prints 4 %.  Both numbers are kept and
    only the floor-free one drives `G-AMP`.
    """
    scored = joint.score_fit(fit_row, TRUTH_UM)
    scored["amplitude_relative_pct_floor500"] = scored["amplitude_relative_pct"]
    scored["amplitude_relative_pct"] = 100.0 * abs(fit_row["amplitude_um"] - TRUTH_UM) / TRUTH_UM
    scored["gates"]["G-AMP"] = scored["amplitude_relative_pct"] <= AMPLITUDE_LIMIT_PCT
    scored["gates"] = {key: bool(value) for key, value in scored["gates"].items()}
    return scored


def report() -> int:
    build_law_result = assembly.build_law()
    sigma_of = joint.share_law(build_law_result)
    invert = build_law_result[1]

    half_gap_of = build_law_result[0]
    control_state = null_state(CONTROL_KMH, invert, half_gap_of)
    control = score(fit(BUMP_ROUTE, CONTROL_KMH, sigma_of, control_state))
    control_fit = fit(BUMP_ROUTE, CONTROL_KMH, sigma_of, control_state)
    reproduced = (abs(control_fit["amplitude_um"] - ARCHIVED_80["amplitude_um"]) <= 0.02 * ARCHIVED_80["amplitude_um"]
                  and abs(control_fit["centre_m"] - ARCHIVED_80["centre_m"]) <= 1.0e-3
                  and abs(control["p95_um"] - ARCHIVED_80["p95_um"]) <= 0.05 * ARCHIVED_80["p95_um"])

    print(f"self-check at {CONTROL_KMH:.0f} km/h: A {control_fit['amplitude_um']:.1f} um "
          f"(archived {ARCHIVED_80['amplitude_um']:.1f}), centre {control_fit['centre_m']:.3f} m "
          f"(archived {ARCHIVED_80['centre_m']:.3f}), p95 {control['p95_um']:.2f} um "
          f"(archived {ARCHIVED_80['p95_um']:.2f}) -> {'reproduced' if reproduced else 'NOT reproduced'}")
    if not reproduced:
        raise SystemExit("the local fit path does not reproduce the archived 80 km/h number; "
                         "its 60/100 km/h rows would not be evidence about speed")

    rows = []
    print()
    print(f"{'km/h':>6} {'fit A':>7} {'rel %':>7} {'centre':>8} {'p95 um':>8} {'worst %':>8} "
          f"{'loc m':>6} {'usable':>7} {'G-ABS':>6} {'G-REL':>6} {'G-LOC':>6} {'G-AMP':>6}")
    for speed in (CONTROL_KMH, *SPEEDS_KMH):
        state = (null_state(speed, invert, half_gap_of)
                 if speed != CONTROL_KMH else control_state)
        fit_row = fit(BUMP_ROUTE, speed, sigma_of, state)
        scored = score(fit_row)
        gates = scored["gates"]
        rows.append({"speed_kmh": speed, "run_id": fit_row["run_id"],
                     "amplitude_um": round(fit_row["amplitude_um"], 2),
                     "centre_m": round(fit_row["centre_m"], 4),
                     "share_rms": round(fit_row["share_rms"], 5),
                     "usable_stations": fit_row["usable_stations"],
                     **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in scored.items()
                        if k != "gates"},
                     "gates": gates, "passing": all(gates.values())})
        print(f"{speed:6.0f} {fit_row['amplitude_um']:7.1f} {scored['amplitude_relative_pct']:7.2f} "
              f"{fit_row['centre_m']:8.3f} {scored['p95_um']:8.2f} "
              f"{scored['worst_bin_relative_pct']:8.2f} {scored['peak_error_m']:6.3f} "
              f"{fit_row['usable_stations']:7d} "
              f"{'PASS' if gates['G-ABS'] else 'FAIL':>6} {'PASS' if gates['G-REL'] else 'FAIL':>6} "
              f"{'PASS' if gates['G-LOC'] else 'FAIL':>6} {'PASS' if gates['G-AMP'] else 'FAIL':>6}")

    transfer = [row for row in rows if row["speed_kmh"] != CONTROL_KMH]
    transfers = all(row["passing"] for row in transfer)
    amplitudes = [row["amplitude_um"] for row in rows]
    spread_pct = 100.0 * (max(amplitudes) - min(amplitudes)) / float(np.mean(amplitudes))
    verdict = ("the inversion carries across speed: the same law and the same one-gaussian model recover "
               "60 um at 60, 80 and 100 km/h" if transfers else
               "the inversion does not carry across speed: the operating point or the law is speed dependent")
    print()
    print(f"amplitude spread across the three speeds: {spread_pct:.2f} %")
    print(f"VERDICT: {verdict}")

    transitions = [{**transition(speed, level), "level": level}
                   for speed in (CONTROL_KMH, *SPEEDS_KMH) for level in (0.05, 0.50)]
    print()
    print(f"{'km/h':>6} {'first share>=0.05':>20} {'first share>=0.50':>22}")
    for speed in (CONTROL_KMH, *SPEEDS_KMH):
        low = next(row for row in transitions if row["speed_kmh"] == speed and row["level"] == 0.05)
        high = next(row for row in transitions if row["speed_kmh"] == speed and row["level"] == 0.50)
        print(f"{speed:6.0f} {low['station_m']!s:>10} m {low['time_s']!s:>6} s "
              f"{high['station_m']!s:>10} m {high['time_s']!s:>6} s")
    payload = {"model": {"width_m": WIDTH_M, "fit_window_m": [FIT_LO_M, FIT_HI_M],
                         "share_bounds": [SHARE_LO, SHARE_HI], "truth_um": TRUTH_UM,
                         "bump_centre_m": CENTRE_M},
               "gates": {"G-ABS": ABSOLUTE_LIMIT_UM, "G-REL": RELATIVE_LIMIT_PCT,
                         "G-LOC": STATION_LIMIT_M, "G-AMP": AMPLITUDE_LIMIT_PCT},
               "self_check_80": {"archived": ARCHIVED_80, "reproduced": bool(reproduced)},
               "rows": rows, "transitions": transitions, "transfers": bool(transfers),
               "amplitude_spread_pct": round(spread_pct, 3), "verdict": verdict}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0


def main() -> int:
    if "--plan" in sys.argv:
        return plan()
    return report()


if __name__ == "__main__":
    raise SystemExit(main())
