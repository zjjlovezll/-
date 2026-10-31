"""M8 step 3: give the inversion a forward model that composes, then recount the peaks.

Round 274 showed the peak count is not identifiable because the *measured* share law does not compose:
fed the true three-peak profile it misses the measured share by rms 0.0317, and BIC then buys gaussians
to absorb that error.  A better selection rule cannot fix that.

So this round replaces the law with a two-body Hertz model, which composes by construction:

    F_stock = C_stock * max(0, p - max(0, -g))^1.5
    F_blade = C_blade * max(0, p - max(0,  g))^1.5
    F_stock + F_blade = N            (solve for the common wheel-centre height p)
    share   = F_blade / N            with g = d(s) - z(s) the blade gap

The two stiffnesses are fitted on the **single-bump** 50 um run (truth known), never on the profile being
tested.  Then, in order:

    1. composition check: fed the truth, does this forward match the measured share better than the law?
    2. mode selection: BIC over K = 1..5 gaussians of the declared width, on the three-peak run.
       Gates unchanged from round 274: G-COUNT / G-LOC / G-AMP / G-ABS / G-SEP.

Both halves can fail honestly: if the fitted stiffnesses are unphysical, or if the forward still misses the
measured share, then the count stays unidentified and that is what gets reported.
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
import s130_two_peak as two  # noqa: E402
import s131_peak_count as peaks  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "composable_forward.json"

CALIBRATION_ROUTE = "one_set_bump050.0um"
CALIBRATION_PEAK = ((58.5, 50.0),)          # single bump, width from base.SIGMA_M
TWO_PEAK_ROUTE = two.ROUTE                  # one_set_twopeak
THREE_PEAK_ROUTE = peaks.ROUTE              # one_set_threepeak_obs

WIDTH_M = two.WIDTH_M
FIT_LO_M = peaks.FIT_LO_M
FIT_HI_M = peaks.FIT_HI_M
SHARE_LO = joint.SHARE_LO
SHARE_HI = joint.SHARE_HI
C_LOW, C_HIGH = 2.0e9, 6.0e11               # wider than round 253: those fits leaned on the wrong physics
STIFFNESS_REFERENCE = 1.1267e11             # the frozen static contact stiffness, for scale only
MAX_PEAKS = peaks.MAX_PEAKS

ABSOLUTE_LIMIT_UM = assembly.ABSOLUTE_LIMIT_UM
RELATIVE_LIMIT_PCT = joint.RELATIVE_LIMIT_PCT
STATION_LIMIT_M = assembly.STATION_LIMIT_M
WINDOW_FRACTION = assembly.WINDOW_FRACTION
MIN_SEPARATION_M = peaks.MIN_SEPARATION_M


def share_model(gap_m: np.ndarray, load_n: np.ndarray, c_stock: float, c_blade: float) -> np.ndarray:
    """Share carried by the blade, from two Hertz contacts sharing one normal load."""
    gap = np.asarray(gap_m, dtype=float)
    load = np.asarray(load_n, dtype=float)
    stock_floor = np.maximum(0.0, -gap)
    blade_floor = np.maximum(0.0, gap)
    share = np.full_like(gap, np.nan)

    for index in range(gap.size):
        target = float(load[index])
        if not np.isfinite(target) or target <= 0.0:
            continue
        low, high = 0.0, max(stock_floor[index], blade_floor[index]) + 1.0
        for _ in range(80):
            mid = 0.5 * (low + high)
            total = (c_stock * max(0.0, mid - stock_floor[index]) ** 1.5
                     + c_blade * max(0.0, mid - blade_floor[index]) ** 1.5)
            if total < target:
                low = mid
            else:
                high = mid
        height = 0.5 * (low + high)
        blade_force = c_blade * max(0.0, height - blade_floor[index]) ** 1.5
        stock_force = c_stock * max(0.0, height - stock_floor[index]) ** 1.5
        total_force = blade_force + stock_force
        if total_force > 0.0:
            share[index] = blade_force / total_force
    return share


def _state(route: str) -> dict:
    run = base._load(base._run_id(route))
    stations = np.asarray(run["station"], dtype=float)
    observed = base._smooth(base._split(run), stations, base.SMOOTH_M)
    load = run["stock"] + run["blade"]
    return {"route": route, "stations": stations, "observed": observed, "load": load,
            "gap": base._gap_profile(stations)}


def _profile(stations: np.ndarray, truth) -> np.ndarray:
    total = np.zeros_like(stations)
    for centre, amplitude in truth:
        total += amplitude * np.exp(-0.5 * ((stations - centre) / WIDTH_M) ** 2)
    return total


def _mask(state: dict) -> np.ndarray:
    stations, observed = state["stations"], state["observed"]
    return (np.isfinite(observed) & (stations >= FIT_LO_M) & (stations <= FIT_HI_M)
            & (observed >= SHARE_LO) & (observed <= SHARE_HI))


def fit_stiffness() -> dict:
    """Fit C_stock and C_blade on the single 50 um bump -- never on the profile under test."""
    state = _state(CALIBRATION_ROUTE)
    mask = _mask(state)
    gap = state["gap"][mask] - 1e-6 * _profile(state["stations"], CALIBRATION_PEAK)[mask]
    load, share = state["load"][mask], state["observed"][mask]

    def residual(log_c: np.ndarray) -> np.ndarray:
        predicted = share_model(gap, load, float(np.exp(log_c[0])), float(np.exp(log_c[1])))
        return np.where(np.isfinite(predicted), predicted - share, 0.0)

    start = np.log([1.0e11, 1.0e11])
    solved = least_squares(residual, start, method="trf", xtol=1e-12, ftol=1e-12)
    c_stock, c_blade = float(np.exp(solved.x[0])), float(np.exp(solved.x[1]))
    rms = float(np.sqrt(np.mean(residual(solved.x) ** 2)))
    return {"c_stock": c_stock, "c_blade": c_blade, "share_rms_on_calibration": rms,
            "stations": int(mask.sum()), "reference": STIFFNESS_REFERENCE}


def composition(state: dict, truth, c_stock: float, c_blade: float) -> dict:
    mask = _mask(state)
    gap = state["gap"][mask] - 1e-6 * _profile(state["stations"], truth)[mask]
    predicted = share_model(gap, state["load"][mask], c_stock, c_blade)
    error = predicted - state["observed"][mask]
    good = np.isfinite(error)
    return {"route": state["route"], "share_rms": float(np.sqrt(np.mean(error[good] ** 2))),
            "share_max": float(np.max(np.abs(error[good]))), "stations": int(good.sum())}


def fit_count(state: dict, count: int, c_stock: float, c_blade: float) -> dict:
    mask = _mask(state)
    stations, load = state["stations"][mask], state["load"][mask]
    gap_plain, share = state["gap"][mask], state["observed"][mask]
    if count == 0:
        predicted = share_model(gap_plain, load, c_stock, c_blade)
        good = np.isfinite(predicted)
        return {"count": 0, "cost": float(np.sum((predicted[good] - share[good]) ** 2)),
                "bic": float("-inf"), "peaks": [], "usable": int(good.sum()), "params": []}

    def residual(amplitudes: np.ndarray, centres: list[float]) -> np.ndarray:
        bump = np.zeros_like(stations)
        for index, centre in enumerate(centres):
            bump += amplitudes[index] * np.exp(-0.5 * ((stations - centre) / WIDTH_M) ** 2)
        predicted = share_model(gap_plain - 1e-6 * bump, load, c_stock, c_blade)
        return np.where(np.isfinite(predicted), predicted - share, 0.0)

    def refit(centres: list[float], amplitudes: list[float]) -> tuple[float, np.ndarray]:
        start = np.asarray(amplitudes, dtype=float)
        solved = least_squares(residual, start, args=(centres,),
                               bounds=(np.full(start.size, 1.0), np.full(start.size, 400.0)),
                               method="trf", xtol=1e-12, ftol=1e-12)
        return float(np.sum(solved.fun ** 2)), solved.x

    grid = np.arange(FIT_LO_M + 0.2, FIT_HI_M - 0.2 + 1e-9, 0.1)
    centres: list[float] = []
    amplitudes: list[float] = []
    cost = float(np.sum(residual(np.zeros(0), []) ** 2))
    while len(centres) < count:
        best = None
        for centre in grid:
            if any(abs(centre - held) < 0.2 for held in centres):
                continue
            trial_cost, trial_amp = refit(centres + [float(centre)], amplitudes + [40.0])
            if best is None or trial_cost < best[0]:
                best = (trial_cost, centres + [float(centre)], [float(v) for v in trial_amp])
        cost, centres, amplitudes = best[0], best[1], best[2]

    pairs = sorted([(float(centre), float(amplitude)) for centre, amplitude in zip(centres, amplitudes)])
    n = int(mask.sum())
    bic = n * np.log(cost / n) + 2 * count * np.log(n) if cost > 0.0 else float("-inf")
    return {"count": count, "cost": cost, "bic": float(bic), "peaks": pairs, "usable": n,
            "params": [value for centre, amplitude in pairs for value in (amplitude, centre)]}


def _judge(fits: list[dict], truth, stations: np.ndarray, c_stock: float, c_blade: float,
           gap_plain: np.ndarray, load: np.ndarray) -> dict:
    chosen = min(fits, key=lambda row: row["bic"])
    fitted = _profile(stations, chosen["peaks"])
    wanted = _profile(stations, truth)

    peak = float(np.max(np.abs(wanted)))
    window = np.abs(wanted) >= WINDOW_FRACTION * peak
    p95 = float(np.percentile(np.abs(fitted[window] - wanted[window]), 95.0))

    remaining = sorted([(centre, amplitude) for centre, amplitude in truth])
    per_peak = []
    for centre_hat, amplitude_hat in chosen["peaks"]:
        if not remaining:
            break
        centre_true, amplitude_true = min(remaining, key=lambda row: abs(row[0] - centre_hat))
        remaining.remove((centre_true, amplitude_true))
        per_peak.append({"centre_true_m": centre_true, "centre_fit_m": centre_hat,
                         "location_error_m": abs(centre_hat - centre_true),
                         "amplitude_true_um": amplitude_true, "amplitude_fit_um": amplitude_hat,
                         "amplitude_relative_pct": 100.0 * abs(amplitude_hat - amplitude_true)
                         / max(amplitude_true, assembly.Y_REF_UM)})
    centres = [row[0] for row in chosen["peaks"]]
    separated = len(centres) < 2 or min(b - a for a, b in zip(centres, centres[1:])) >= MIN_SEPARATION_M
    gates = {"G-COUNT": chosen["count"] == len(truth),
             "G-LOC": all(row["location_error_m"] <= STATION_LIMIT_M for row in per_peak),
             "G-AMP": all(row["amplitude_relative_pct"] <= RELATIVE_LIMIT_PCT for row in per_peak),
             "G-ABS": p95 <= ABSOLUTE_LIMIT_UM,
             "G-SEP": separated}
    return {"selected_count": chosen["count"], "per_peak": per_peak, "p95_um": p95, "gates": gates,
            "bic": {str(row["count"]): row["bic"] for row in fits},
            "cost": {str(row["count"]): row["cost"] for row in fits}}


def main(argv: list[str]) -> int:
    if "--report" not in argv:
        print(__doc__)
        return 0

    stiffness = fit_stiffness()
    c_stock, c_blade = stiffness["c_stock"], stiffness["c_blade"]
    print(f"fitted on the 50 um single bump: C_stock {c_stock:.3e}  C_blade {c_blade:.3e} "
          f"(reference {STIFFNESS_REFERENCE:.3e}, share rms {stiffness['share_rms_on_calibration']:.4f})")

    two_state = _state(TWO_PEAK_ROUTE)
    three_state = _state(THREE_PEAK_ROUTE)
    comp_two = composition(two_state, two.PEAKS, c_stock, c_blade)
    comp_three = composition(three_state, peaks.PEAKS, c_stock, c_blade)
    print("\ncomposition on the true profile (share units)")
    for row in (comp_two, comp_three):
        print(f"  {row['route']:26s} rms {row['share_rms']:.4f}  max {row['share_max']:.4f}  n {row['stations']}")

    fits = [fit_count(three_state, count, c_stock, c_blade) for count in range(1, MAX_PEAKS + 1)]
    mask = _mask(three_state)
    judged = _judge(fits, peaks.PEAKS, three_state["stations"], c_stock, c_blade,
                    three_state["gap"], three_state["load"])

    print("\nmode selection on the three-peak run with the composable forward (truth: 3)")
    print(f"{'K':>3} {'SSE':>12} {'BIC':>13}")
    for row in fits:
        print(f"{row['count']:>3} {row['cost']:12.4e} {row['bic']:13.2f}")
    print(f"\n{'peak':>4} {'s_true':>8} {'s_fit':>8} {'d s m':>7} {'A_true':>7} {'A_fit':>7} {'rel %':>7}")
    for index, row in enumerate(judged["per_peak"], start=1):
        print(f"{index:>4} {row['centre_true_m']:8.3f} {row['centre_fit_m']:8.3f} "
              f"{row['location_error_m']:7.3f} {row['amplitude_true_um']:7.1f} "
              f"{row['amplitude_fit_um']:7.1f} {row['amplitude_relative_pct']:7.2f}")
    print(f"\nselected {judged['selected_count']}  p95 {judged['p95_um']:.2f} um")
    print("/".join(f"{name}: {'PASS' if ok else 'FAIL'}" for name, ok in judged["gates"].items()))

    verdict = ("the composable forward counts the peaks: three on the three-peak profile"
               if all(judged["gates"].values()) else
               "the composable forward still does not count the peaks; the count stays unidentified")
    print(f"VERDICT: {verdict}")

    payload = {"stiffness": stiffness, "composition": {"two_peak": comp_two, "three_peak": comp_three},
               "three_peak": judged, "peaks_true": peaks.PEAKS, "width_m_prior": WIDTH_M,
               "verdict": verdict, "run_id": base._run_id(THREE_PEAK_ROUTE),
               "usable_stations": int(mask.sum())}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
