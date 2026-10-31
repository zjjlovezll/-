"""M8 step 2: count the peaks instead of declaring them.

Round 273 fitted a two-peak profile whose peak *count* was given.  A measured corrugated surface does
not come with its peak count, so the next question is whether the number can be chosen from the data.

Structure (pre-registered before the run):

    truth, three peaks, all at the declared width 0.35 m
        40 um at 58.50 m  +  30 um at 59.50 m  +  20 um at 60.50 m

Attempt 1 of this round put the first peak at 57.40 m and is kept here as the design lesson: the null
share there is 0.000, i.e. below the observable floor, so nothing constrains that amplitude -- the fit
ran it to the 400 um bound (398.2 um, p95 346 um) while still counting the peaks correctly.  The design
below stays inside the band where the blade is actually carrying (share between 0.02 and 0.98, roughly
58.2-60.7 m), which is where an amplitude can be measured at all.

    estimator: K gaussians of the same declared width, 2K parameters (A_i, s_i), K = 1..5
    selection: BIC = n ln(SSE / n) + 2K ln(n)      (lowest BIC wins)

    G-COUNT  the selected K equals the true count (2 on the round-273 run, 3 on this one)
    G-LOC    each selected peak within 0.20 m of its true peak
    G-AMP    each selected amplitude within 2 % of its truth
    G-ABS    p95 of the selected model <= 22 um where the truth exceeds 10 % of its peak

The selector is first run on the *already archived* two-peak profile (round 273), where the answer is
known to be 2, and only then on the new three-peak profile.  A selector that cannot count two cannot be
trusted to count three, and this check costs no simulation.

Why the count matters for the goal: the deliverable is a band surface z(s) on the rode contact band, and
a parametric fit whose peak count is supplied by hand is not a surface estimate -- it is a fit to a
description someone already wrote down.

What this round deliberately does not do: fit the widths (they stay the declared 0.35 m), and cover a
random broadband profile whose peaks are not countable -- that needs a non-parametric estimator and is
the next step.
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
import s124_joint_inversion as joint  # noqa: E402
import s130_two_peak as two  # noqa: E402

CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s131"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "peak_count.json"

ROUTE = "one_set_threepeak_obs"
PEAKS = ((58.5, 40.0), (59.5, 30.0), (60.5, 20.0))    # (centre m, amplitude um) -- fixed before the run
WIDTH_M = 0.35
SPEED_KMH = base.SPEED_KMH
DURATION_S = base.DURATION_S

MAX_PEAKS = 5
FIT_LO_M = 55.5
FIT_HI_M = 61.5
SHARE_LO, SHARE_HI = joint.SHARE_LO, joint.SHARE_HI

ABSOLUTE_LIMIT_UM = assembly.ABSOLUTE_LIMIT_UM
RELATIVE_LIMIT_PCT = joint.RELATIVE_LIMIT_PCT
STATION_LIMIT_M = assembly.STATION_LIMIT_M
Y_REF_UM = assembly.Y_REF_UM
WINDOW_FRACTION = assembly.WINDOW_FRACTION
MIN_SEPARATION_M = 0.5


def truth_profile(stations: np.ndarray, peaks=PEAKS) -> np.ndarray:
    total = np.zeros_like(stations)
    for centre, amplitude in peaks:
        total += amplitude * np.exp(-0.5 * ((stations - centre) / WIDTH_M) ** 2)
    return total


def model(params: np.ndarray, stations: np.ndarray) -> np.ndarray:
    total = np.zeros_like(stations)
    for index in range(0, len(params), 2):
        amplitude, centre = params[index], params[index + 1]
        total += amplitude * np.exp(-0.5 * ((stations - centre) / WIDTH_M) ** 2)
    return total


def build() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    case = json.loads(CASE.read_text(encoding="utf-8"))
    touched = 0
    for body in case["rail_templates"][1].get("bodies") or []:
        if body.get("id") != "blade":
            continue
        for station in body["stations"]:
            s_m = float(station["s_m"])
            height = sum(amplitude * 1e-6 * np.exp(-0.5 * ((s_m - centre) / WIDTH_M) ** 2)
                         for centre, amplitude in PEAKS)
            station["profile"]["z_offset_m"] = float(station["profile"].get("z_offset_m", 0.0)) + height
            touched += 1
    case["case_id"] = f"{case['case_id']}_{ROUTE}"
    case["purpose_detail"] = (case.get("purpose_detail", "") +
                             f" | peak-count variant: {PEAKS} um, width {WIDTH_M} m")
    path = OUT / f"{ROUTE}.json"
    path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    sampled = np.array([float(station["s_m"]) for body in case["rail_templates"][1]["bodies"]
                        for station in body["stations"] if body.get("id") == "blade"])
    profile = np.array([sum(amplitude * 1e-6 * np.exp(-0.5 * ((s - centre) / WIDTH_M) ** 2)
                            for centre, amplitude in PEAKS) for s in sampled])
    print(f"three peaks {PEAKS} um at width {WIDTH_M} m -> {path.name} ({touched} blade stations)")
    for centre, amplitude in PEAKS:
        index = int(np.argmin(np.abs(sampled - centre)))
        print(f"  near {centre:.2f} m the stations carry {1e6 * profile[index]:5.2f} um")
    print(f"  valley {1e6 * profile.min():5.2f} um at {sampled[int(np.argmin(profile))]:.3f} m")
    return 0


def observed_state(route: str) -> dict:
    """The two things an inversion needs: the measured share and the null operating point."""
    null_state = two._null_state()
    run = base._load(base._run_id(route))
    stations = np.asarray(run["station"], dtype=float)
    return {"stations": stations,
            "observed": base._smooth(base._split(run), stations, base.SMOOTH_M),
            "widths": law._width_at(stations, *law._width_table()),
            "u0": null_state["u0"]}


def fit_count(state: dict, count: int) -> dict:
    """Forward stepwise selection with a joint refit at every step.

    With the width fixed the model is only mildly nonlinear, but a cold 2K-parameter solve lands in
    local minima (round 1 of this round: every K reported the same SSE, i.e. the extra peaks were
    never used).  So the peaks are placed one at a time: for each candidate centre the whole set is
    refitted, and the centre that lowers the residual the most is kept.  That is standard forward
    selection, and it stays cheap because each refit is small.
    """
    stations = state["stations"]
    observed = state["observed"]
    usable = (np.isfinite(observed) & np.isfinite(state["u0"])
              & (stations >= FIT_LO_M) & (stations <= FIT_HI_M)
              & (observed >= SHARE_LO) & (observed <= SHARE_HI))
    sigma_of = joint.share_law(assembly.build_law())
    u0, widths, share = state["u0"][usable], state["widths"][usable], observed[usable]
    grid = np.arange(FIT_LO_M + 0.2, FIT_HI_M - 0.2 + 1e-9, 0.1)
    n = int(usable.sum())

    def residual(params: np.ndarray, centres: list[float]) -> np.ndarray:
        bump = np.zeros_like(stations[usable])
        for index, centre in enumerate(centres):
            bump += params[index] * np.exp(-0.5 * ((stations[usable] - centre) / WIDTH_M) ** 2)
        return sigma_of(u0 + bump, widths) - share

    def refit(centres: list[float], amplitudes: list[float]) -> tuple[float, np.ndarray]:
        start = np.asarray(amplitudes, dtype=float)
        solved = least_squares(residual, start, args=(centres,),
                               bounds=(np.full(start.size, 1.0), np.full(start.size, 400.0)),
                               method="trf", xtol=1e-12, ftol=1e-12)
        return float(np.sum(solved.fun ** 2)), solved.x

    centres: list[float] = []
    amplitudes: list[float] = []
    cost = float(np.sum(residual(np.zeros(0), []) ** 2))
    while len(centres) < count:
        best = None
        for centre in grid:
            if any(abs(centre - held) < 0.2 for held in centres):
                continue
            trial_c = centres + [float(centre)]
            trial_a = amplitudes + [40.0]
            trial_cost, trial_amp = refit(trial_c, trial_a)
            if best is None or trial_cost < best[0]:
                best = (trial_cost, trial_c, trial_amp)
        cost, centres, amplitudes = best[0], best[1], [float(v) for v in best[2]]

    order = np.argsort(centres)
    pairs = sorted([(float(centres[i]), float(amplitudes[i])) for i in order])
    bic = n * np.log(cost / n) + 2 * count * np.log(n) if cost > 0.0 else float("-inf")
    return {"count": count, "cost": cost, "bic": float(bic), "peaks": pairs, "usable": n,
            "params": [value for centre, amplitude in pairs for value in (amplitude, centre)]}


def composition_error(route: str, peaks) -> dict:
    """How far the measured share law is from the simulated share when the bumps superpose.

    The law was calibrated one bump at a time (rounds 254-256).  If it composes, then feeding it the
    true profile reproduces the measured share up to the noise of the share estimate; if it does not,
    every extra gaussian in the fit buys a piece of that error, and the peak count is over-selected for
    a reason that has nothing to do with counting.
    """
    state = observed_state(route)
    stations, observed = state["stations"], state["observed"]
    sigma_of = joint.share_law(assembly.build_law())
    mask = (np.isfinite(observed) & np.isfinite(state["u0"])
            & (stations >= FIT_LO_M) & (stations <= FIT_HI_M)
            & (observed >= SHARE_LO) & (observed <= SHARE_HI))
    predicted = sigma_of(state["u0"] + truth_profile(stations, peaks), state["widths"])
    error = predicted[mask] - observed[mask]
    return {"route": route, "share_rms": float(np.sqrt(np.mean(error ** 2))),
            "share_max": float(np.max(np.abs(error))), "stations": int(mask.sum())}


def judge(fits: list[dict], truth, stations: np.ndarray) -> dict:
    chosen = min(fits, key=lambda row: row["bic"])
    count = chosen["count"]
    fitted = model(np.asarray(chosen["params"], dtype=float), stations)
    wanted = truth_profile(stations, truth)

    peak = float(np.max(np.abs(wanted)))
    window = np.abs(wanted) >= WINDOW_FRACTION * peak
    error = fitted[window] - wanted[window]
    p95 = float(np.percentile(np.abs(error), 95.0))

    remaining = sorted([(centre, amplitude) for centre, amplitude in truth])
    per_peak = []
    separated = True
    for centre_hat, amplitude_hat in sorted(chosen["peaks"]):
        if not remaining:
            break
        centre_true, amplitude_true = min(remaining, key=lambda row: abs(row[0] - centre_hat))
        remaining.remove((centre_true, amplitude_true))
        per_peak.append({"centre_true_m": centre_true, "centre_fit_m": centre_hat,
                         "location_error_m": abs(centre_hat - centre_true),
                         "amplitude_true_um": amplitude_true, "amplitude_fit_um": amplitude_hat,
                         "amplitude_relative_pct": 100.0 * abs(amplitude_hat - amplitude_true)
                         / max(amplitude_true, Y_REF_UM)})
    centres = [row[0] for row in chosen["peaks"]]
    if len(centres) > 1:
        separated = min(b - a for a, b in zip(centres, centres[1:])) >= MIN_SEPARATION_M

    gates = {"G-COUNT": count == len(truth),
             "G-LOC": all(row["location_error_m"] <= STATION_LIMIT_M for row in per_peak),
             "G-AMP": all(row["amplitude_relative_pct"] <= RELATIVE_LIMIT_PCT for row in per_peak),
             "G-ABS": p95 <= ABSOLUTE_LIMIT_UM,
             "G-SEP": separated}
    return {"selected_count": count, "bic_margin": float(sorted(row["bic"] for row in fits)[1]
                                                         - chosen["bic"]) if len(fits) > 1 else None,
            "per_peak": per_peak, "p95_um": p95, "gates": gates,
            "bic": {str(row["count"]): row["bic"] for row in fits},
            "cost": {str(row["count"]): row["cost"] for row in fits}}


def report() -> int:
    two_state = observed_state(two.ROUTE)
    three_state = observed_state(ROUTE)

    two_fits = [fit_count(two_state, count) for count in range(1, MAX_PEAKS + 1)]
    three_fits = [fit_count(three_state, count) for count in range(1, MAX_PEAKS + 1)]

    two_judged = judge(two_fits, two.PEAKS, two_state["stations"])
    three_judged = judge(three_fits, PEAKS, three_state["stations"])

    print("selector on the archived two-peak run (truth: 2)")
    print(f"{'K':>3} {'SSE':>12} {'BIC':>13}")
    for row in two_fits:
        print(f"{row['count']:>3} {row['cost']:12.4e} {row['bic']:13.2f}")
    print(f"selected {two_judged['selected_count']}  p95 {two_judged['p95_um']:.2f} um")
    print("/".join(f"{k}: {'PASS' if v else 'FAIL'}" for k, v in two_judged["gates"].items()))
    print()

    print("selector on the three-peak run (truth: 3)")
    print(f"{'K':>3} {'SSE':>12} {'BIC':>13}")
    for row in three_fits:
        print(f"{row['count']:>3} {row['cost']:12.4e} {row['bic']:13.2f}")
    print(f"\n{'peak':>4} {'s_true':>8} {'s_fit':>8} {'d s m':>7} {'A_true':>7} {'A_fit':>7} {'rel %':>7}")
    for index, row in enumerate(three_judged["per_peak"], start=1):
        print(f"{index:>4} {row['centre_true_m']:8.3f} {row['centre_fit_m']:8.3f} "
              f"{row['location_error_m']:7.3f} {row['amplitude_true_um']:7.1f} "
              f"{row['amplitude_fit_um']:7.1f} {row['amplitude_relative_pct']:7.2f}")
    print(f"\nselected {three_judged['selected_count']}  p95 {three_judged['p95_um']:.2f} um  "
          f"margin {three_judged['bic_margin']:.1f}")
    print("/".join(f"{k}: {'PASS' if v else 'FAIL'}" for k, v in three_judged["gates"].items()))

    verdict = ("the selector counts the peaks: two on the archived profile, three on this one"
               if all(two_judged["gates"].values()) and all(three_judged["gates"].values()) else
               "the selector does not count the peaks; the profile's peak number is not yet identified")
    print(f"VERDICT: {verdict}")

    composition = [composition_error(two.ROUTE, two.PEAKS),
                   composition_error("one_set_threepeak", ((57.4, 45.0), (58.5, 30.0), (59.7, 55.0))),
                   composition_error(ROUTE, PEAKS)]
    print("composition error of the measured law on the true profile (share units)")
    for row in composition:
        print(f"  {row['route']:26s} rms {row['share_rms']:.4f}  max {row['share_max']:.4f}  "
              f"n {row['stations']}")

    payload = {"route": ROUTE, "run_id": base._run_id(ROUTE), "peaks_true": PEAKS,
               "composition": {row["route"]: row for row in composition},
               "width_m_prior": WIDTH_M, "fit_window_m": [FIT_LO_M, FIT_HI_M],
               "max_peaks": MAX_PEAKS, "two_peak": two_judged, "three_peak": three_judged,
               "verdict": verdict}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0


def main(argv: list[str]) -> int:
    if "--build" in argv:
        return build()
    if "--report" in argv:
        return report()
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
