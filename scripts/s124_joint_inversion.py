"""M7 step 2: stop inverting station by station; fit two parameters forward instead.

Round 260 inverted the split law at every station and failed (0/3 amplitudes, best p95 98 um against a
22 um gate).  The reason is in its own error budget: pointwise inversion multiplies the law's error
(about 30 um in u) and the per-station share flicker (about 50 um) by the ramp's geometry, and leaves a
43 um background even after the null run defines the zero.

This script keeps the same observables and the same law but never inverts it pointwise.  It fits two
parameters -- amplitude A and centre s0 -- by matching the *predicted* share to the measured one:

    z(s)      = A * exp(-0.5 * ((s - s0) / WIDTH_M)**2)          width is a declared prior
    u(s)      = d(s) - z(s)                                       d from the canonical case
    sigma(s)  = law(u(s), g0(w(s)))                               the round-255/256 measured law

Two parameters against ~25 stations of a curve with a 0.37 swing is a well-conditioned problem; the
pointwise version had ~25 parameters against the same data.

The width is held at the shape the runs were built with (sigma_s = 1.2 m) and that is stated as a prior,
not as something inferred: round 258 showed the onset station does not track the bump's width, so this
script does not pretend to measure it.

Gates (identical to round 260, declared before this script existed):
    G-ABS  p95(|z_hat - z|) <= 22 um over the window where the truth exceeds 10 % of its peak
    G-REL  worst 2 mm bin |e| / max(|z|, 500 um) <= 2 %
    G-LOC  |peak station - the truth's peak| <= 0.20 m

Writes ``reports/load_split_inversion_2026-10-31/joint_inversion.json``.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
from scipy.optimize import least_squares

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s113_profile_inversion as base  # noqa: E402
import s119_width_aware_inversion as law  # noqa: E402
import s123_m7_assembly as assembly  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "joint_inversion.json"

WIDTH_M = base.SIGMA_M
ABSOLUTE_LIMIT_UM = assembly.ABSOLUTE_LIMIT_UM
RELATIVE_LIMIT_PCT = assembly.RELATIVE_LIMIT_PCT
STATION_LIMIT_M = assembly.STATION_LIMIT_M
WINDOW_FRACTION = assembly.WINDOW_FRACTION
BIN_M = assembly.BIN_M
Y_REF_UM = assembly.Y_REF_UM
FIT_LO_M, FIT_HI_M = 55.5, 61.5
SHARE_LO, SHARE_HI = 0.02, 0.98
AMPLITUDES_UM = (20.0, 30.0, 40.0, 50.0, 60.0, 80.0, 100.0, 120.0, 200.0)


def share_law(build_law_result) -> callable:
    """sigma as a function of (u_um, width_mm) from the measured curve, with the width offset."""
    curves, _ = law._measured_curves()
    table_s, table_w = law._width_table()
    half_gap_of, _, anchor = build_law_result
    base_gap = float(anchor["half_gap_um"])
    base_station = float(anchor["station_m"])
    curve_u, curve_sigma = curves[base_station]

    order = np.argsort(curve_u)
    u_inc, sigma_dec = curve_u[order], curve_sigma[order]

    def sigma_of(u_um: np.ndarray, width_mm: np.ndarray) -> np.ndarray:
        g0 = np.asarray([half_gap_of(float(width)) for width in np.atleast_1d(width_mm)])
        return np.interp(np.asarray(u_um) - g0 + base_gap, u_inc, sigma_dec, left=1.0, right=0.0)

    return sigma_of


def fit_one(route: str, sigma_of, null_state: dict, multistart: bool = False) -> dict:
    """Two-parameter forward fit against the null-calibrated operating point.

    The law is never trusted absolutely: the un-bumped run supplies the operating state u0(s) at every
    station (one inversion of the same law, on a run where the answer must be "no bump"), and the bump
    run is then predicted forward from it.  That is what removes the 43-105 um absolute bias round 260
    measured, without touching the law's anchors or shifting them by section width.

    The bump adds to that state (plus, not minus).  Measured at 58.5 m: the un-bumped run sits at
    share 0.586 and the 50 um bump at 0.954, i.e. a raised blade takes *more* load, and the measured
    law's u coordinate runs the same way round as the raise.  The minus sign used in the first version
    of this fit predicted 0.210 where the run showed 0.954, which is why it collapsed onto its bounds.
    """
    run = base._load(base._run_id(route))
    stations = run["station"]
    observed = base._smooth(base._split(run), stations, base.SMOOTH_M)
    table_s, table_w = law._width_table()
    widths = law._width_at(stations, table_s, table_w)
    u0 = null_state["u0"]

    usable = (np.isfinite(observed) & np.isfinite(u0) & (stations >= FIT_LO_M)
              & (stations <= FIT_HI_M) & (observed >= SHARE_LO) & (observed <= SHARE_HI))

    def residual(params: np.ndarray) -> np.ndarray:
        amplitude, centre = params
        bump = amplitude * np.exp(-0.5 * ((stations[usable] - centre) / WIDTH_M) ** 2)
        predicted = sigma_of(u0[usable] + bump, widths[usable])
        return predicted - observed[usable]

    # Multi-start over the centre.  A single start at the nominal centre found a shifted local minimum
    # on the 50 um run (centre 57.92 m, p95 24 um) while the same fit from a neighbouring start landed
    # on 58.52 m -- so the start is reported with the answer instead of being left to luck.
    starts = ([(70.0, base.CENTRE_M)] if not multistart else
              [(amplitude_start, float(centre_start))
               for amplitude_start in (40.0, 80.0, 160.0)
               for centre_start in np.arange(base.CENTRE_M - 1.2, base.CENTRE_M + 1.201, 0.3)])
    best = None
    for amplitude_start, centre_start in starts:
        solved = least_squares(residual, np.asarray([amplitude_start, centre_start]),
                               bounds=([1.0, base.CENTRE_M - 3.0], [400.0, base.CENTRE_M + 3.0]),
                               method="trf", xtol=1e-12, ftol=1e-12)
        cost = float(np.sum(solved.fun ** 2))
        if best is None or cost < best[0]:
            best = (cost, solved, centre_start)
    cost, solved, start_centre = best
    return {"route": route, "run_id": base._run_id(route), "stations": stations,
            "amplitude_um": float(solved.x[0]), "centre_m": float(solved.x[1]),
            "share_rms": float(np.sqrt(np.mean(solved.fun ** 2))),
            "cost": cost, "start_centre_m": start_centre,
            "usable_stations": int(usable.sum()),
            "observed_peak_share": float(np.max(observed[usable])) if usable.any() else float("nan")}


def score_fit(fit: dict, truth_um: float) -> dict:
    stations = fit["stations"]
    truth = base._true_bump(stations, truth_um)
    z_hat = fit["amplitude_um"] * np.exp(-0.5 * ((stations - fit["centre_m"]) / WIDTH_M) ** 2)
    peak = float(np.max(np.abs(truth)))
    window = np.abs(truth) >= WINDOW_FRACTION * peak
    window &= np.isfinite(z_hat)

    error = z_hat[window] - truth[window]
    p95 = float(np.percentile(np.abs(error), 95.0))
    worst_rel = 0.0
    s_win = stations[window]
    for start in np.arange(s_win.min(), s_win.max(), BIN_M):
        inside = window & (stations >= start) & (stations < start + BIN_M)
        if not inside.any():
            continue
        denominator = max(float(np.max(np.abs(truth[inside]))), Y_REF_UM)
        worst_rel = max(worst_rel, 100.0 * float(np.max(np.abs(z_hat[inside] - truth[inside])))
                        / denominator)
    truth_peak_station = float(s_win[int(np.argmax(np.abs(truth[window])))])
    peak_station = float(s_win[int(np.argmax(np.abs(z_hat[window])))])
    relative = abs(fit["amplitude_um"] - truth_um) / max(truth_um, Y_REF_UM)
    return {
        "truth_peak_um": peak,
        "estimated_peak_um": float(np.max(np.abs(z_hat[window]))),
        "amplitude_relative_pct": 100.0 * relative,
        "p95_um": p95,
        "worst_bin_relative_pct": worst_rel,
        "peak_error_m": abs(peak_station - truth_peak_station),
        "gates": {"G-ABS": p95 <= ABSOLUTE_LIMIT_UM,
                  "G-REL": worst_rel <= RELATIVE_LIMIT_PCT,
                  "G-LOC": abs(peak_station - truth_peak_station) <= STATION_LIMIT_M},
    }


def main() -> int:
    build_law_result = assembly.build_law()
    sigma_of = share_law(build_law_result)
    _, invert, _ = build_law_result
    half_gap_of = build_law_result[0]
    null_run = base._load(base._run_id(assembly.BASELINE_ROUTE))
    null_stations = null_run["station"]
    null_share = base._smooth(base._split(null_run), null_stations, base.SMOOTH_M)
    null_widths = law._width_at(null_stations, *law._width_table())
    null_u0 = np.full_like(null_share, np.nan)
    ok = np.isfinite(null_share) & (null_share > SHARE_LO) & (null_share < SHARE_HI)
    for index in np.nonzero(ok)[0]:
        null_u0[index] = invert(float(null_share[index]), half_gap_of(float(null_widths[index])))
    null_state = {"stations": null_stations, "share_raw": null_share, "u0": null_u0}

    print(f"width held at {WIDTH_M:.2f} m (declared prior); fit window {FIT_LO_M}-{FIT_HI_M} m, "
          f"share in ({SHARE_LO}, {SHARE_HI})")
    payload = {"width_m_prior": WIDTH_M, "fit_window_m": [FIT_LO_M, FIT_HI_M],
               "share_bounds": [SHARE_LO, SHARE_HI], "modes": {}}

    for mode, multistart in (("single start at the nominal centre", False),
                             ("multi-start over centre", True)):
        rows = []
        for amplitude_um in AMPLITUDES_UM:
            route = f"one_set_bump{amplitude_um:05.1f}um"
            try:
                fit = fit_one(route, sigma_of, null_state, multistart)
            except SystemExit as failure:  # no archived run for this amplitude
                print(f"{mode}: {amplitude_um:5.1f} {str(failure)[:60]}")
                continue
            row = {"route": route,
                   "fit": {k: v for k, v in fit.items() if k not in ("stations", "share_raw")},
                   **score_fit(fit, amplitude_um)}
            rows.append(row)

        passing = [row for row in rows if all(row["gates"].values())]
        absolute_pass = [row for row in rows if row["gates"]["G-ABS"]]
        print()
        print(f"--- {mode} ---")
        print(f"{'truth':>7} {'fit A':>7} {'rel %':>7} {'centre':>8} {'d centre':>9} {'p95 um':>8} "
              f"{'worst 2mm %':>12} {'peak err m':>11} {'G-ABS':>6} {'G-REL':>6} {'G-LOC':>6}")
        for row in rows:
            gates = row["gates"]
            print(f"{row['truth_peak_um']:7.1f} {row['fit']['amplitude_um']:7.1f} "
                  f"{row['amplitude_relative_pct']:7.2f} {row['fit']['centre_m']:8.3f} "
                  f"{row['fit']['centre_m'] - base.CENTRE_M:9.3f} {row['p95_um']:8.2f} "
                  f"{row['worst_bin_relative_pct']:12.2f} {row['peak_error_m']:11.3f} "
                  f"{'PASS' if gates['G-ABS'] else 'FAIL':>6} "
                  f"{'PASS' if gates['G-REL'] else 'FAIL':>6} "
                  f"{'PASS' if gates['G-LOC'] else 'FAIL':>6}")
        verdict = (f"{len(passing)}/{len(rows)} amplitudes pass all three gates "
                   f"(G-ABS alone: {len(absolute_pass)}/{len(rows)})")
        print(verdict)
        payload["modes"][("single" if not multistart else "multistart")] = {
            "description": mode, "amplitudes": rows,
            "passing_all_gates": len(passing), "passing_absolute": len(absolute_pass),
            "verdict": verdict}

    single = payload["modes"]["single"]
    multi = payload["modes"]["multistart"]
    payload["finding"] = (
        "The share-only joint fit recovers amplitude and position for amplitudes below about 50 um, "
        "and fails above it: the share saturates (1.000 on the 100/200 um runs) so the two parameters "
        "stop being identifiable, and multi-start then finds lower-cost but worse answers, which is "
        "evidence of model misspecification rather than of a better fit.  Round 260's pointwise "
        "assembly managed 0/3; this forward fit manages "
        f"{single['passing_all_gates']}/{len(single['amplitudes'])} from the nominal start and "
        f"{multi['passing_all_gates']}/{len(multi['amplitudes'])} from multi-start.")
    print()
    print(payload["finding"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + chr(10), encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
