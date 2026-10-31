"""M8 step 4: two stages -- count with the composable forward, size with the measured law.

Rounds 274-275 left the two halves in opposite places:

    measured law        sizes a single bump to 0.45 % (rounds 261/273) but does not compose, so a free
                        BIC over K selects 5 instead of 3
    two-body Hertz      composes, so the count comes out 3, but it misses even its own calibration bump
                        (share rms 0.1065) and sizes the peaks at 16.3 / 27.3 / 15.2 um instead of
                        40 / 30 / 20

So use each where it works, in that order, and let the gates judge the result:

    stage 1  count   : composable forward, BIC over K = 1..5          -> K = 3, centres as the initial guess
    stage 2  size    : measured law, K fixed at stage 1's count, centres/amplitudes refined jointly

Pre-registered, before running:

    G-COUNT  stage 1 selects 3
    G-LOC    each sized peak within 0.20 m of its truth
    G-AMP    each sized amplitude within 2 % of its truth
    G-ABS    p95 of the sized profile <= 22 um where the truth exceeds 10 % of its peak
    G-SEP    the three sized centres stay >= 0.5 m apart

Two stage-2 variants are declared and both reported, because choosing between them after seeing the
numbers would be exactly the kind of post-hoc selection this project forbids:

    2a joint  : one least-squares over (A_i, c_i) with the law, initialised at stage-1 centres
    2b greedy : measured-law forward selection with K pinned at stage-1's count (the round-274 machinery,
                stopped at 3 instead of allowed to run to 5)

No new simulation: every run used here is already archived.
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
import s123_m7_assembly as assembly  # noqa: E402
import s124_joint_inversion as joint  # noqa: E402
import s131_peak_count as count_stage  # noqa: E402
import s132_composable_forward as forward  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "two_stage.json"
ROUTE = count_stage.ROUTE                     # one_set_threepeak_obs
TRUTH = count_stage.PEAKS                     # 40 / 30 / 20 um at 58.5 / 59.5 / 60.5 m

WIDTH_M = count_stage.WIDTH_M
FIT_LO_M = count_stage.FIT_LO_M
FIT_HI_M = count_stage.FIT_HI_M
SHARE_LO = joint.SHARE_LO
SHARE_HI = joint.SHARE_HI
MAX_PEAKS = count_stage.MAX_PEAKS


def _mask(state: dict) -> np.ndarray:
    """Stations the measured law can be evaluated at: observed share, null operating point and window.

    The null operating point is part of the mask because the law is applied as sigma(u0 + z): where the
    null share itself is below the observable floor there is no u0, and including such a station makes the
    residual non-finite rather than merely uninformative.
    """
    stations, observed = state["stations"], state["observed"]
    return (np.isfinite(observed) & np.isfinite(state["u0"])
            & (stations >= FIT_LO_M) & (stations <= FIT_HI_M)
            & (observed >= SHARE_LO) & (observed <= SHARE_HI))


def stage_one(state: dict) -> dict:
    stiffness = forward.fit_stiffness()
    fits = [forward.fit_count(state, count, stiffness["c_stock"], stiffness["c_blade"])
            for count in range(1, MAX_PEAKS + 1)]
    chosen = min(fits, key=lambda row: row["bic"])
    return {"stiffness": stiffness, "selected": chosen["count"],
            "peaks": [[centre, amplitude] for centre, amplitude in chosen["peaks"]],
            "bic": {str(row["count"]): row["bic"] for row in fits}}


def _law_forward() -> callable:
    sigma_of = joint.share_law(assembly.build_law())
    return sigma_of


def stage_two_joint(state: dict, peaks: list[list[float]]) -> dict:
    sigma_of = _law_forward()
    mask = _mask(state)
    stations, u0 = state["stations"][mask], state["u0"][mask]
    widths, share = state["widths"][mask], state["observed"][mask]

    def residual(params: np.ndarray) -> np.ndarray:
        bump = np.zeros_like(stations)
        for index in range(0, len(params), 2):
            bump += params[index] * np.exp(-0.5 * ((stations - params[index + 1]) / WIDTH_M) ** 2)
        return sigma_of(u0 + bump, widths) - share

    start = np.array([value for centre, amplitude in peaks for value in (amplitude, centre)], dtype=float)
    lower = np.tile(np.array([1.0, FIT_LO_M]), len(peaks))
    upper = np.tile(np.array([400.0, FIT_HI_M]), len(peaks))
    solved = least_squares(residual, start, bounds=(lower, upper), method="trf", xtol=1e-12, ftol=1e-12)
    fitted = sorted([(float(solved.x[i + 1]), float(solved.x[i])) for i in range(0, len(solved.x), 2)])
    return {"peaks": [[centre, amplitude] for centre, amplitude in fitted],
            "cost": float(np.sum(solved.fun ** 2)), "stations": int(mask.sum())}


def stage_two_greedy(state: dict, count: int) -> dict:
    sigma_of = _law_forward()
    mask = _mask(state)
    stations, u0 = state["stations"][mask], state["u0"][mask]
    widths, share = state["widths"][mask], state["observed"][mask]
    grid = np.arange(FIT_LO_M + 0.2, FIT_HI_M - 0.2 + 1e-9, 0.1)

    def residual(amplitudes: np.ndarray, centres: list[float]) -> np.ndarray:
        bump = np.zeros_like(stations)
        for index, centre in enumerate(centres):
            bump += amplitudes[index] * np.exp(-0.5 * ((stations - centre) / WIDTH_M) ** 2)
        return sigma_of(u0 + bump, widths) - share

    centres: list[float] = []
    amplitudes: list[float] = []
    cost = float(np.sum(residual(np.zeros(0), []) ** 2))
    while len(centres) < count:
        best = None
        for centre in grid:
            if any(abs(centre - held) < 0.2 for held in centres):
                continue
            start = np.asarray(amplitudes + [40.0], dtype=float)
            solved = least_squares(residual, start, args=(centres + [float(centre)],),
                                   bounds=(np.full(start.size, 1.0), np.full(start.size, 400.0)),
                                   method="trf", xtol=1e-12, ftol=1e-12)
            trial = float(np.sum(solved.fun ** 2))
            if best is None or trial < best[0]:
                best = (trial, centres + [float(centre)], [float(v) for v in solved.x])
        cost, centres, amplitudes = best[0], best[1], best[2]
    peaks = sorted([(float(centre), float(amplitude)) for centre, amplitude in zip(centres, amplitudes)])
    return {"peaks": [[centre, amplitude] for centre, amplitude in peaks],
            "cost": cost, "stations": int(mask.sum())}


def judge(result: dict, stations: np.ndarray) -> dict:
    settled = sorted([(centre, amplitude) for centre, amplitude in result["peaks"]])
    truth = sorted([(centre, amplitude) for centre, amplitude in TRUTH])
    fitted = count_stage.truth_profile(stations, tuple(settled))
    wanted = count_stage.truth_profile(stations, tuple(truth))

    peak = float(np.max(np.abs(wanted)))
    window = np.abs(wanted) >= count_stage.WINDOW_FRACTION * peak
    p95 = float(np.percentile(np.abs(fitted[window] - wanted[window]), 95.0))

    remaining = list(truth)
    per_peak = []
    for centre_hat, amplitude_hat in settled:
        if not remaining:
            break
        centre_true, amplitude_true = min(remaining, key=lambda row: abs(row[0] - centre_hat))
        remaining.remove((centre_true, amplitude_true))
        per_peak.append({"centre_true_m": centre_true, "centre_fit_m": centre_hat,
                         "location_error_m": abs(centre_hat - centre_true),
                         "amplitude_true_um": amplitude_true, "amplitude_fit_um": amplitude_hat,
                         "amplitude_relative_pct": 100.0 * abs(amplitude_hat - amplitude_true)
                         / max(amplitude_true, assembly.Y_REF_UM)})
    centres = [row[0] for row in settled]
    separated = len(centres) < 2 or min(b - a for a, b in zip(centres, centres[1:])) >= count_stage.MIN_SEPARATION_M
    gates = {"G-LOC": all(row["location_error_m"] <= assembly.STATION_LIMIT_M for row in per_peak),
             "G-AMP": all(row["amplitude_relative_pct"] <= joint.RELATIVE_LIMIT_PCT for row in per_peak),
             "G-ABS": p95 <= assembly.ABSOLUTE_LIMIT_UM,
             "G-SEP": separated}
    return {"peaks": result["peaks"], "per_peak": per_peak, "p95_um": p95, "gates": gates,
            "cost": result["cost"], "stations": result["stations"]}


def main(argv: list[str]) -> int:
    if "--report" not in argv:
        print(__doc__)
        return 0

    # stage 1 needs the per-frame load (the composable forward divides by it); stage 2 needs the null
    # operating point and the section widths (the measured law is calibrated in those coordinates).
    rich = count_stage.observed_state(ROUTE)
    state = dict(forward._state(ROUTE), u0=rich["u0"], widths=rich["widths"])
    first = stage_one(state)
    print(f"stage 1 (composable forward): selected K = {first['selected']}")
    for centre, amplitude in first["peaks"]:
        print(f"   {centre:7.3f} m  {amplitude:6.1f} um")
    print("   BIC " + "  ".join(f"K={key}: {value:.1f}" for key, value in first["bic"].items()))

    both = {"joint": stage_two_joint(state, first["peaks"]),
            "greedy": stage_two_greedy(state, first["selected"])}

    print("\nstage 2 (measured law, count fixed)")
    print(f"{'variant':>8} {'peak':>5} {'s_fit':>8} {'d s m':>7} {'A_fit':>7} {'A_true':>7} {'rel %':>7} "
          f"{'p95':>7}")
    payload = {"route": ROUTE, "run_id": base._run_id(ROUTE), "truth": TRUTH,
               "stage_one": first, "stage_two": {}, "gates": {}}
    for name, result in both.items():
        judged = judge(result, state["stations"])
        for index, row in enumerate(judged["per_peak"], start=1):
            print(f"{name:>8} {index:>5} {row['centre_fit_m']:8.3f} {row['location_error_m']:7.3f} "
                  f"{row['amplitude_fit_um']:7.1f} {row['amplitude_true_um']:7.1f} "
                  f"{row['amplitude_relative_pct']:7.2f} {judged['p95_um']:7.2f}")
        print(f"{name:>8} gates " + "/".join(f"{key}: {'PASS' if ok else 'FAIL'}"
                                             for key, ok in judged["gates"].items()))
        payload["stage_two"][name] = judged
        payload["gates"][name] = judged["gates"]

    best = min(payload["stage_two"], key=lambda name: payload["stage_two"][name]["p95_um"])
    payload["best_by_p95"] = best
    complete = all(payload["stage_two"][best]["gates"].values()) and first["selected"] == len(TRUTH)
    verdict = (f"two stages work: {best} sizes the three peaks and every gate passes"
               if complete else
               f"two stages give the count ({first['selected']}) but not every gate; best variant {best} "
               f"p95 {payload['stage_two'][best]['p95_um']:.2f} um")
    payload["verdict"] = verdict
    print(f"\nVERDICT: {verdict}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
