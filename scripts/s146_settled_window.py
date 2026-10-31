"""The speed question again, now with the start-up transient kept out of the window.

Round 290 found why one 80 km/h calibration did not transfer: on the un-bumped run the blade first carries at
the same *time* at every speed (0.367 s), not at the same station, so the operating point u0(s) is the
transient's shape shifted along the track by the travel speed.  This round is the fix that finding specified:
start 10 m earlier, let the transient die, and analyse only stations reached after t = 0.45 s.

Pre-registered before any run (same four gates as round 290, nothing loosened):

    start        x_start = seat_x_start_m = 30 m  (front axle at 40 m; >= 0.6 s before 50 m at 60 km/h)
    window       t >= 0.45 s only; inside it the usual 55.5-61.5 m and share in (0.02, 0.98)
    model / law  unchanged from round 261 / 290
    u0(s)        from each speed's OWN un-bumped settled run
    speeds       60, 80 (control) and 100 km/h

    G-ABS   p95 <= 22 um        G-REL  worst 2 mm bin <= 2 %
    G-LOC   <= 0.20 m           G-AMP  |A - 60| / 60 <= 2 %

The prediction is falsifiable in both directions: if the transient was the whole story, all three speeds pass
and the amplitude gate is met; if 60 km/h still plateaus short of 1.000 (round 290 measured 0.704), the window
will not rescue it and "single speed only" becomes the conclusion.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import s145_speed_transfer as transfer  # noqa: E402
import s110_lowering_readings as lowering  # noqa: E402
import s113_profile_inversion as base  # noqa: E402
import s119_width_aware_inversion as law  # noqa: E402
import s123_m7_assembly as assembly  # noqa: E402
import s124_joint_inversion as joint  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "scratch" / "s146"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "settled_window.json"

START_M = 30.0
SETTLE_S = 0.45
SPEEDS_KMH = (60.0, 80.0, 100.0)
# Shortest run that still reaches 62 m from a 30 m start: (62 - 40) / v, rounded up a little.
DURATIONS_S = {60.0: 1.35, 80.0: 1.00, 100.0: 0.80}
NULL_ROUTE = "one_set_x30"
BUMP_ROUTE = "one_set_x30_bump060.0um"
TRUTH_UM = transfer.TRUTH_UM
CENTRE_M = transfer.CENTRE_M
WIDTH_M = transfer.WIDTH_M
FIT_LO_M = transfer.FIT_LO_M
FIT_HI_M = transfer.FIT_HI_M
SHARE_LO = transfer.SHARE_LO
SHARE_HI = transfer.SHARE_HI

# Where the two source cases live, and which file each variant derives from.
NULL_SOURCE = lowering.CASE
BUMP_SOURCE = ROOT.parent / "scratch" / "s120" / "one_set_bump060.0um.json"


def build() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for label, source in ((NULL_ROUTE, NULL_SOURCE), (BUMP_ROUTE, BUMP_SOURCE)):
        payload = json.loads(pathlib.Path(source).read_text(encoding="utf-8"))
        payload["case_id"] = f"{payload['case_id']}_x30"
        payload["purpose_detail"] = ("settled-window variant of the canonical one-set case: starts 10 m "
                                     "earlier so the start-up transient dies before the analysed stations")
        payload["run"]["x_start_m"] = START_M
        payload["run"]["seat_x_start_m"] = START_M
        target = OUT / f"{label}.json"
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"{label}: x_start {payload['run']['x_start_m']:.1f} m -> {target.name} "
              f"(source {pathlib.Path(source).name})")
    return 0


def plan() -> int:
    for speed in SPEEDS_KMH:
        for route, case in ((NULL_ROUTE, OUT / f"{NULL_ROUTE}.json"),
                            (BUMP_ROUTE, OUT / f"{BUMP_ROUTE}.json")):
            print(f"python -X utf8 scripts/s99_run_archive.py --case {case.as_posix()} "
                  f"--speed-kmh {speed:.0f} --duration {DURATIONS_S[speed]:.2f} "
                  f"--note campaign=settled-window")
    return 0


def select(route: str, speed_kmh: float) -> str:
    if speed_kmh not in DURATIONS_S:
        raise SystemExit(f"speed {speed_kmh:g} km/h is outside the pre-registered set "
                         f"{sorted(DURATIONS_S)}")
    duration = DURATIONS_S[speed_kmh]
    rows = [row for row in base._index_rows()
            if row.get("route") == route
            and abs(float(row["duration_s"]) - duration) < 1e-9
            and abs(float(row["speed_kmh"]) - speed_kmh) < 1e-9]
    if not rows:
        raise SystemExit(f"no archived {duration:.2f} s run for {route!r} at {speed_kmh:g} km/h")
    return str(rows[-1]["run_id"])


def load_settled(route: str, speed_kmh: float) -> dict:
    run = transfer.load(select(route, speed_kmh), speed_kmh)
    run["settled"] = run["times"] >= SETTLE_S
    return run


def null_state(speed_kmh: float, invert, half_gap_of) -> dict:
    run = load_settled(NULL_ROUTE, speed_kmh)
    observed = transfer.share(run)
    widths = law._width_at(run["station"], *law._width_table())
    u0 = np.full_like(observed, np.nan)
    ok = run["settled"] & np.isfinite(observed) & (observed > SHARE_LO) & (observed < SHARE_HI)
    for index in np.nonzero(ok)[0]:
        u0[index] = invert(float(observed[index]), half_gap_of(float(widths[index])))
    return {"stations": run["station"], "share": observed, "u0": u0, "settled": run["settled"]}


def fit(speed_kmh: float, sigma_of, state: dict) -> dict:
    from scipy.optimize import least_squares

    run = load_settled(BUMP_ROUTE, speed_kmh)
    stations = run["station"]
    observed = transfer.share(run)
    widths = law._width_at(stations, *law._width_table())
    u0 = state["u0"]
    usable = (run["settled"] & np.isfinite(observed) & np.isfinite(u0)
              & (stations >= FIT_LO_M) & (stations <= FIT_HI_M)
              & (observed >= SHARE_LO) & (observed <= SHARE_HI))

    if float(np.max(run["blade"])) <= 0.0:
        return {"route": BUMP_ROUTE, "speed_kmh": speed_kmh, "run_id": run["run_id"],
                "stations": stations, "amplitude_um": float("nan"), "centre_m": float("nan"),
                "share_rms": float("nan"), "usable_stations": 0,
                "measurable": False, "reason": "the blade never carries in this run"}

    def residual(params: np.ndarray) -> np.ndarray:
        amplitude, centre = params
        bump = amplitude * np.exp(-0.5 * ((stations[usable] - centre) / WIDTH_M) ** 2)
        return sigma_of(u0[usable] + bump, widths[usable]) - observed[usable]

    solved = least_squares(residual, np.asarray([70.0, CENTRE_M]),
                           bounds=([1.0, CENTRE_M - 3.0], [400.0, CENTRE_M + 3.0]),
                           method="trf", xtol=1e-12, ftol=1e-12)
    return {"route": BUMP_ROUTE, "speed_kmh": speed_kmh, "run_id": run["run_id"],
            "stations": stations, "amplitude_um": float(solved.x[0]),
            "centre_m": float(solved.x[1]),
            "share_rms": float(np.sqrt(np.mean(solved.fun ** 2))),
            "usable_stations": int(usable.sum()), "measurable": True, "reason": "ok"}


def score(fit_row: dict) -> dict:
    scored = joint.score_fit(fit_row, TRUTH_UM)
    scored["amplitude_relative_pct_floor500"] = scored["amplitude_relative_pct"]
    scored["amplitude_relative_pct"] = 100.0 * abs(fit_row["amplitude_um"] - TRUTH_UM) / TRUTH_UM
    scored["gates"]["G-AMP"] = scored["amplitude_relative_pct"] <= transfer.AMPLITUDE_LIMIT_PCT
    scored["gates"] = {key: bool(value) for key, value in scored["gates"].items()}
    return scored


def settle_diagnosis(speed_kmh: float) -> dict:
    """Where the blade first carries on the settled null run, and the plateau it reaches."""
    run = load_settled(NULL_ROUTE, speed_kmh)
    stations, observed = run["station"], transfer.share(run)
    first = np.nonzero(np.isfinite(observed) & (observed >= 0.05))[0]
    plateau = float(np.nanmax(observed[run["settled"]])) if run["settled"].any() else float("nan")
    return {"speed_kmh": speed_kmh,
            "first_station_m": round(float(stations[first[0]]), 4) if first.size else None,
            "first_time_s": round(float(run["times"][first[0]]), 4) if first.size else None,
            "plateau_share": round(plateau, 4)}


def report() -> int:
    build_law_result = assembly.build_law()
    sigma_of = joint.share_law(build_law_result)
    half_gap_of, invert = build_law_result[0], build_law_result[1]

    rows, diagnoses, unmeasured = [], [], []
    print(f"{'km/h':>6} {'fit A':>7} {'rel %':>7} {'centre':>8} {'p95 um':>8} {'worst %':>8} "
          f"{'loc m':>6} {'usable':>7} {'G-ABS':>6} {'G-REL':>6} {'G-LOC':>6} {'G-AMP':>6}")
    for speed in SPEEDS_KMH:
        try:
            state = null_state(speed, invert, half_gap_of)
            fit_row = fit(speed, sigma_of, state)
        except SystemExit as missing:
            print(f"{speed:6.0f}  not archived yet ({missing})")
            continue
        if not fit_row["measurable"]:
            print(f"{speed:6.0f}  not measurable: {fit_row['reason']}")
            unmeasured.append({"speed_kmh": speed, "run_id": fit_row["run_id"],
                               "reason": fit_row["reason"]})
            continue
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
        try:
            diagnoses.append(settle_diagnosis(speed))
        except SystemExit as missing:
            print(f"[{speed:.0f} km/h] settled diagnosis skipped: {missing}")
        print(f"{speed:6.0f} {fit_row['amplitude_um']:7.1f} {scored['amplitude_relative_pct']:7.2f} "
              f"{fit_row['centre_m']:8.3f} {scored['p95_um']:8.2f} "
              f"{scored['worst_bin_relative_pct']:8.2f} {scored['peak_error_m']:6.3f} "
              f"{fit_row['usable_stations']:7d} "
              f"{'PASS' if gates['G-ABS'] else 'FAIL':>6} {'PASS' if gates['G-REL'] else 'FAIL':>6} "
              f"{'PASS' if gates['G-LOC'] else 'FAIL':>6} {'PASS' if gates['G-AMP'] else 'FAIL':>6}")

    print()
    print(f"{'km/h':>6} {'first carry (station)':>22} {'time':>7} {'plateau share':>14}")
    for row in diagnoses:
        print(f"{row['speed_kmh']:6.0f} {row['first_station_m']!s:>22} {row['first_time_s']!s:>7} "
              f"{row['plateau_share']!s:>14}")

    passing = [row for row in rows if row["passing"]]
    spreads = [row["amplitude_um"] for row in rows]
    spread_pct = 100.0 * (max(spreads) - min(spreads)) / float(np.mean(spreads)) if len(spreads) > 1 else 0.0
    speakers = ", ".join(f"{row['speed_kmh']:.0f}" for row in unmeasured)
    if not rows:
        verdict = ("nothing measurable yet"
                   + (f" ({speakers} km/h: blade never carries)" if unmeasured else ""))
    elif len(passing) == len(rows):
        verdict = ("the settled window rescues the transfer: 60, 80 and 100 km/h all clear the four gates"
                   f" (amplitude spread {spread_pct:.2f} %)")
    elif len(passing) >= 1 and len(rows) < len(SPEEDS_KMH):
        names = ", ".join(f"{row['speed_kmh']:.0f}" for row in passing)
        verdict = (f"incomplete: {len(rows)} of {len(SPEEDS_KMH)} speeds archived, and only {names} km/h "
                   "clears every gate so far")
    elif len(passing) >= 1:
        names = ", ".join(f"{row['speed_kmh']:.0f}" for row in passing)
        verdict = (f"partly: the settled window rescues {names} km/h but not the others, so the operating "
                   "point still carries speed dependence")
    else:
        verdict = ("the settled window rescues nothing: the band inversion stays single speed")
    print()
    print(f"amplitude spread across the three speeds: {spread_pct:.2f} %")
    print(f"VERDICT: {verdict}")

    payload = {"design": {"start_m": START_M, "settle_s": SETTLE_S, "durations_s": DURATIONS_S,
                          "window_m": [FIT_LO_M, FIT_HI_M], "share_bounds": [SHARE_LO, SHARE_HI],
                          "width_m": WIDTH_M, "truth_um": TRUTH_UM},
               "rows": rows, "diagnoses": diagnoses, "unmeasured": unmeasured,
               "passing_speeds": [r["speed_kmh"] for r in passing],
               "amplitude_spread_pct": round(spread_pct, 3), "verdict": verdict}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0


def main() -> int:
    if "--build" in sys.argv:
        return build()
    if "--plan" in sys.argv:
        return plan()
    return report()


if __name__ == "__main__":
    raise SystemExit(main())
