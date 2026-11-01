"""Does the band inversion carry across speed, once the speeds are really different?

Round 43 found that three "different" speeds were one 80 km/h trajectory (B052), and round 48 made the
corrected 60 km/h case integrate at all (modal-scale seat seeds).  This is the comparison that the
question deserves, on a matched window instead of a matched duration:

    the front axle is followed from 56.0 m to 65.0 m at every speed, so all three see the same
    stations (the ramp, the first touch at ~57.7 m, the flush region) and only the clock differs.

That is also what makes it affordable: at 60 km/h the switching region costs >= 3x per simulated second
(round 298 measured 41 min for 1.35 s), so the window is sized in metres and each speed gets the duration
that covers it (60 km/h 0.54 s, 80 km/h 0.41 s, 100 km/h 0.33 s).  The 80 km/h pair already exists on
the same geometry (x30, 1.00 s) and reaches the window, so it is reused rather than re-run.

Pre-registered before the runs land (unchanged from the speed-transfer round):
    model      z = A exp(-0.5 ((s - 58.5)/1.20)^2)
    law        the measured width-resolved split law (s119), never re-fitted here
    working pt u0(s) inverted from that speed's OWN null run, inside the window only
    G-ABS      p95 |z_hat - z| <= 22 um over stations where the truth >= 10 % of its peak
    G-REL      worst 2 mm bin |error| / max(|truth|, 500 um) <= 2 % (truth >= 50 um only)
    G-LOC      |fitted centre - 58.5| <= 0.20 m
    G-AMP      |A_hat - 60| / 60 <= 2 %        <- denominator is the truth, not a floor
and B052 is re-checked on every run this reads: meta speed * 3.6 must equal the claimed speed, and
profile_speed_kmh (when present) must agree with it.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "cross_speed.json"

WINDOW_LO_M = 56.0
WINDOW_HI_M = 65.0
TRUTH_AMPLITUDE_UM = 60.0
CENTRE_M = 58.5
WIDTH_M = 1.20
SPEEDS_KMH = (60.0, 80.0, 100.0)

# speed -> (null route, bump route, duration) ; the 80 km/h pair is the existing x30 one
RUNS = {
    60.0: ("one_set_x46", "one_set_x46_bump060.0um", 0.54),
    80.0: ("one_set_x30", "one_set_x30_bump060.0um", 1.00),
    100.0: ("one_set_x46", "one_set_x46_bump060.0um", 0.33),  # 9 m / 27.778 = 0.324 s, rounded up
}

SHARE_LO = 0.02
SHARE_HI = 0.98
FIT_LO_M = 55.5
FIT_HI_M = 65.5
FLOOR_UM = 500.0
ABSOLUTE_LIMIT_UM = 22.0
RELATIVE_LIMIT_PCT = 2.0
STATION_LIMIT_M = 0.20
AMPLITUDE_LIMIT_PCT = 2.0


def _base():
    import s113_profile_inversion as base

    return base


def select(route: str, speed_kmh: float, duration_s: float) -> dict:
    """Newest archived run for this route/speed/duration, with its B052 self-check."""
    base = _base()
    rows = [row for row in base._index_rows()
            if row.get("route") == route
            and abs(float(row["speed_kmh"]) - speed_kmh) < 1e-9
            and abs(float(row["duration_s"]) - duration_s) < 1e-6]
    if not rows:
        raise SystemExit(f"no archived {duration_s:.2f} s run for {route!r} at {speed_kmh:g} km/h")
    row = rows[-1]
    meta_path = base.RUNS / str(row["run_id"]) / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    recorded = abs(float(meta["speed_m_s"])) * 3.6
    if abs(recorded - speed_kmh) > 1e-6:
        raise SystemExit(f"{row['run_id']} claims {speed_kmh:g} km/h but was driven at {recorded:.3f}"
                         f" -- run the archive speed guard before trusting this table")
    declared = meta.get("profile_speed_kmh")
    if declared is not None and abs(float(declared) - speed_kmh) > 1e-9:
        raise SystemExit(f"{row['run_id']} declares a profile of {declared} km/h, not {speed_kmh:g}")
    return row


def load(route: str, speed_kmh: float, duration_s: float) -> dict:
    import s145_speed_transfer as transfer

    row = select(route, speed_kmh, duration_s)
    run = transfer.load(str(row["run_id"]), speed_kmh)
    run["route"] = route
    return run


def law_tools():
    import s119_width_aware_inversion as law

    import s123_m7_assembly as assembly

    half_gap_of, invert, _anchor = assembly.build_law()
    return law, half_gap_of, invert


def null_state(speed_kmh: float) -> dict:
    law, half_gap_of, invert = law_tools()
    route = RUNS[speed_kmh][0]
    run = load(route, speed_kmh, RUNS[speed_kmh][2])
    from s113_profile_inversion import _smooth, _split

    share = _smooth(_split(run), run["station"], 0.20)
    widths = law._width_at(run["station"], *law._width_table())
    inside = (run["station"] >= WINDOW_LO_M) & (run["station"] <= WINDOW_HI_M)
    usable = inside & np.isfinite(share) & (share > SHARE_LO) & (share < SHARE_HI)
    u0 = np.full_like(share, np.nan)
    for index in np.nonzero(usable)[0]:
        u0[index] = invert(float(share[index]), half_gap_of(float(widths[index])))
    engaged = np.nonzero(inside & np.isfinite(share) & (share >= 0.05))[0]
    return {
        "run_id": run["run_id"],
        "station": run["station"],
        "share": share,
        "u0": u0,
        "inside": inside,
        "usable": int(usable.sum()),
        "engage_station_m": float(run["station"][engaged[0]]) if engaged.size else None,
    }


def fit(speed_kmh: float, state: dict) -> dict:
    from scipy.optimize import least_squares

    from s113_profile_inversion import _smooth, _split

    import s123_m7_assembly as assembly
    import s124_joint_inversion as joint

    import s119_width_aware_inversion as law

    route = RUNS[speed_kmh][1]
    run = load(route, speed_kmh, RUNS[speed_kmh][2])
    stations = run["station"]
    observed = _smooth(_split(run), stations, 0.20)
    u0 = np.interp(stations, state["station"], state["u0"], left=np.nan, right=np.nan)
    sigma_of = joint.share_law(assembly.build_law())   # sigma(u, widths): the width-resolved law
    widths = law._width_at(stations, *law._width_table())
    usable = ((stations >= FIT_LO_M) & (stations <= FIT_HI_M)
              & np.isfinite(observed) & np.isfinite(u0)
              & (observed >= SHARE_LO) & (observed <= 1.0))
    if int(usable.sum()) < 20:
        raise SystemExit(f"{route} at {speed_kmh:g} km/h has only {int(usable.sum())} usable stations")

    def residual(params):
        amplitude, centre = params
        truth = amplitude * np.exp(-0.5 * ((stations[usable] - centre) / WIDTH_M) ** 2)
        predicted = sigma_of(u0[usable] + truth, widths[usable])
        return predicted - observed[usable]

    best = None
    for start_centre in (CENTRE_M - 1.0, CENTRE_M, CENTRE_M + 1.0):
        for start_amplitude in (40.0, 60.0, 90.0):
            solved = least_squares(residual, [start_amplitude, start_centre],
                                   bounds=([1.0, FIT_LO_M], [400.0, FIT_HI_M]), method="trf")
            if best is None or solved.cost < best.cost:
                best = solved
    amplitude, centre = (float(value) for value in best.x)
    truth = TRUTH_AMPLITUDE_UM * np.exp(-0.5 * ((stations - CENTRE_M) / WIDTH_M) ** 2)
    estimate = amplitude * np.exp(-0.5 * ((stations - centre) / WIDTH_M) ** 2)
    error = estimate - truth
    window = usable & (truth >= 0.10 * TRUTH_AMPLITUDE_UM)
    p95 = float(np.percentile(np.abs(error[window]), 95)) if window.any() else float("nan")

    worst = 0.0
    if window.any():
        bins = np.floor(stations[window] / 0.002).astype(int)
        truth_w = truth[window]
        error_w = error[window]
        for value in np.unique(bins):
            pick = bins == value
            denominator = np.maximum(np.abs(truth_w[pick]), FLOOR_UM)
            worst = max(worst, float(np.max(np.abs(error_w[pick]) / denominator)))
    rel = float(abs(amplitude - TRUTH_AMPLITUDE_UM) / TRUTH_AMPLITUDE_UM * 100.0)
    return {
        "speed_kmh": speed_kmh,
        "run_id": run["run_id"],
        "amplitude_um": amplitude,
        "centre_m": centre,
        "amplitude_relative_pct": rel,
        "amplitude_relative_pct_floor500": float(
            abs(amplitude - TRUTH_AMPLITUDE_UM) / max(TRUTH_AMPLITUDE_UM, FLOOR_UM) * 100.0),
        "p95_um": p95,
        "worst_bin_pct": worst * 100.0,
        "station_error_m": float(abs(centre - CENTRE_M)),
        "usable_stations": int(usable.sum()),
        "share_rms": float(np.sqrt(np.mean(error[window] ** 2))) if window.any() else float("nan"),
        "G-ABS": bool(p95 <= ABSOLUTE_LIMIT_UM),
        "G-REL": bool(worst * 100.0 <= RELATIVE_LIMIT_PCT),
        "G-LOC": bool(abs(centre - CENTRE_M) <= STATION_LIMIT_M),
        "G-AMP": bool(rel <= AMPLITUDE_LIMIT_PCT),
    }


def report(speeds: tuple[float, ...] | None = None) -> dict:
    rows = []
    for speed in speeds or SPEEDS_KMH:
        state = null_state(speed)
        row = fit(speed, state)
        row["null_run_id"] = state["run_id"]
        row["null_usable"] = state["usable"]
        row["engage_station_m"] = state["engage_station_m"]
        row["gates"] = all(row[key] for key in ("G-ABS", "G-REL", "G-LOC", "G-AMP"))
        rows.append(row)

    print(f"window {WINDOW_LO_M:.1f}-{WINDOW_HI_M:.1f} m of the front axle, truth "
          f"{TRUTH_AMPLITUDE_UM:.0f} um at {CENTRE_M:.1f} m")
    print(f"{'km/h':>6} {'engage m':>9} {'A um':>7} {'rel %':>7} {'centre':>8} {'p95 um':>7} "
          f"{'worst %':>8} {'G-ABS':>6}{'G-REL':>6}{'G-LOC':>6}{'G-AMP':>6}")
    for row in rows:
        engage = row["engage_station_m"]
        print(f"{row['speed_kmh']:>6.0f} {('%.3f' % engage) if engage else '     -':>9} "
              f"{row['amplitude_um']:>7.1f} {row['amplitude_relative_pct']:>7.2f} "
              f"{row['centre_m']:>8.3f} {row['p95_um']:>7.2f} {row['worst_bin_pct']:>8.2f} "
              f"{str(row['G-ABS']):>6}{str(row['G-REL']):>6}{str(row['G-LOC']):>6}{str(row['G-AMP']):>6}")

    passing = [row["speed_kmh"] for row in rows if row["gates"]]
    amplitude_spread = 100.0 * (max(row["amplitude_um"] for row in rows)
                                - min(row["amplitude_um"] for row in rows)) / TRUTH_AMPLITUDE_UM
    carries = len(passing) == len(rows)
    payload = {
        "window_m": [WINDOW_LO_M, WINDOW_HI_M],
        "truth": {"amplitude_um": TRUTH_AMPLITUDE_UM, "centre_m": CENTRE_M, "width_m": WIDTH_M},
        "rows": rows,
        "passing_speeds": passing,
        "amplitude_spread_pct": amplitude_spread,
        "carries_across_speed": carries,
        "verdict": ("the inversion carries across speed on this window"
                    if carries else
                    f"the inversion does not carry across speed: {passing or 'no speed'} passes"),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\npassing: {passing or 'none'}   amplitude spread {amplitude_spread:.2f} %")
    print(f"VERDICT: {payload['verdict']}")
    print(f"report: {REPORT}")
    return payload


def main() -> int:
    speeds = None
    if len(sys.argv) > 1:
        if sys.argv[1] == "--speeds" and len(sys.argv) > 2:
            speeds = tuple(float(part) for part in sys.argv[2].split(","))
        else:
            raise SystemExit("usage: s152_cross_speed.py [--speeds 60,80,100]")
    payload = report(speeds)
    return 0 if payload["carries_across_speed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
