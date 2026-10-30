"""M5 step 3: a two-parameter monotone map instead of a table fitted on one amplitude.

Round 251 showed that a tabulated ``sigma(u)`` calibrated on the 50 um run cannot extrapolate: the table
simply ends where that run's gap ended, and a bigger bump is clamped to the edge.  The fix is not a
bigger table -- it is a parametrisation that extends beyond its samples.

    sigma(u) = 0.5 * (1 - tanh((u - u0) / w))         u = d(s) - z(s)   (gap seen by the contact)

Two parameters: ``u0`` the gap at which the blade has half the load, ``w`` the width of the transition.
``sigma`` rises as ``u`` falls, and the inverse is closed form,

    u = u0 + w * arctanh(1 - 2 sigma)

so there is no table to run off the end of: the model keeps going where the calibration samples stopped.

Calibration protocol (leave-one-out, pre-registered before running)
-------------------------------------------------------------------
Three amplitudes (50/100/200 um).  For each fold, the map is fitted on the **two** runs it is allowed to
see and applied to the third, which never enters the fit.  Gates are the task book's, unchanged:

    G-A  |peak_est - peak_true| / max(peak_true, 0.5 mm) <= 2 %
    G-B  p95(|e|) <= 22 um over the frames where the truth exceeds 10 % of its peak
    G-C  the station of the inverted peak is within 0.20 m of 58.5 m

The frames used for scoring are those where the blade carries at least half the right-rail load
(``sigma > 0.5``); below that the split cannot tell "no bump" from "small bump", and counting those
frames as measurements would be the round-251 mistake again.
"""
from __future__ import annotations

import itertools
import json
import pathlib
import sys

import numpy as np
from scipy.optimize import least_squares

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s113_profile_inversion as base  # noqa: E402

OUT = ROOT.parent / "scratch" / "s114"
CENTRE_M = base.CENTRE_M
SIGMA_M = base.SIGMA_M
AMPLITUDES_UM = base.AMPLITUDES_UM
CALIBRATION_SHARE = 0.5
RELATIVE_LIMIT = base.RELATIVE_LIMIT
ABSOLUTE_LIMIT_M = base.ABSOLUTE_LIMIT_M
STATION_LIMIT_M = base.STATION_LIMIT_M
WINDOW_FRACTION = base.WINDOW_FRACTION
FLOOR_M = base.FLOOR_M


def _model(u: np.ndarray, u0: float, w: float) -> np.ndarray:
    return 0.5 * (1.0 - np.tanh((u - u0) / w))


def _fit(samples: list[tuple[np.ndarray, np.ndarray]]) -> tuple[float, float]:
    """Fit (u0, w) to the supplied (u, sigma) pairs."""

    def residual(parameters: np.ndarray) -> np.ndarray:
        u0, width = parameters
        pieces = []
        for u, sigma in samples:
            pieces.append(_model(u, u0, width) - sigma)
        return np.concatenate(pieces)

    start = np.array([0.0, 3.0e-5])
    solution = least_squares(residual, start, bounds=([-2.0e-3, 2.0e-6], [2.0e-3, 2.0e-3]),
                             xtol=1e-14, ftol=1e-14, gtol=1e-14, max_nfev=4000)
    return float(solution.x[0]), float(solution.x[1])


def _invert(sigma: np.ndarray, u0: float, w: float) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return u0 + w * np.arctanh(1.0 - 2.0 * sigma)



def transfer_station_readout(run: dict, gap: np.ndarray, share: float = 0.5) -> dict:
    """Amplitude read off the *station* where the blade takes half the load, with no fitted parameter.

    The blade starts carrying when the gap the contact sees closes to zero, i.e. when ``z(s) = d(s)``.
    So the station where the split crosses one half gives one point of the profile directly from the
    known geometry -- and the peak amplitude is *not* recoverable from one pass, because the crossing
    happens on the flank of the bump, not at its top.  That is a property of the measurement, not of the
    estimator, and it is why an ensemble is needed for the peak.
    """
    smoothed = base._smooth(base._split(run), run["station"], base.SMOOTH_M)
    above = np.isfinite(smoothed) & np.isfinite(gap) & (smoothed >= share)
    if not above.any():
        return {"station_m": float("nan"), "z_estimate_m": float("nan")}
    index = int(np.argmax(above))
    return {"station_m": float(run["station"][index]), "z_estimate_m": float(gap[index])}

def main() -> int:
    gap_of = base._gap_profile
    runs, gaps = {}, {}
    for amplitude in AMPLITUDES_UM:
        run = base._load(base._run_id(f"one_set_bump{amplitude:05.1f}um"))
        runs[amplitude] = run
        gaps[amplitude] = gap_of(run["station"])
        print(f"{amplitude:6.1f} um  {run['run_id']}  frames {run['station'].size}")

    def samples_for(amplitudes: tuple[float, ...]) -> list[tuple[np.ndarray, np.ndarray]]:
        out = []
        for amplitude in amplitudes:
            run = runs[amplitude]
            u = gaps[amplitude] - base._true_bump(run["station"], amplitude * 1e-6)
            sigma = base._smooth(base._split(run), run["station"], base.SMOOTH_M)
            keep = np.isfinite(u) & np.isfinite(sigma)
            out.append((u[keep], sigma[keep]))
        return out

    print()
    print("fold   calibration        u0 (um)   w (um)   held out   peak_true  peak_est   p95 (um)  at s   gates")
    rows = []
    for held in AMPLITUDES_UM:
        calibration = tuple(amplitude for amplitude in AMPLITUDES_UM if amplitude != held)
        u0, w = _fit(samples_for(calibration))
        run = runs[held]
        sigma = base._smooth(base._split(run), run["station"], base.SMOOTH_M)
        u_est = _invert(sigma, u0, w)
        truth = base._true_bump(run["station"], held * 1e-6)
        estimate = gaps[held] - u_est
        observed = np.isfinite(sigma) & (sigma > CALIBRATION_SHARE)
        finite = observed & np.isfinite(estimate) & np.isfinite(truth) & ~np.isnan(gaps[held])
        window = finite & (truth > WINDOW_FRACTION * truth.max())
        peak_true = float(truth.max())
        peak_est = float(np.nanmax(estimate[finite])) if finite.any() else float("nan")
        peak_at = float(run["station"][finite][int(np.nanargmax(estimate[finite]))]) if finite.any() else float("nan")
        errors = np.abs(estimate[window] - truth[window]) if window.any() else np.array([np.nan])
        p95 = float(np.percentile(errors, 95))
        relative = abs(peak_est - peak_true) / max(peak_true, FLOOR_M)
        gates = (relative <= RELATIVE_LIMIT, p95 <= ABSOLUTE_LIMIT_M,
                 abs(peak_at - CENTRE_M) <= STATION_LIMIT_M)
        rows.append({"held_out_um": held, "calibration_um": list(calibration),
                     "u0_um": u0 * 1e6, "w_um": w * 1e6, "peak_true_m": peak_true,
                     "peak_estimate_m": peak_est, "relative_error": relative, "p95_error_m": p95,
                     "peak_station_m": peak_at, "gate_relative": bool(gates[0]),
                     "gate_absolute": bool(gates[1]), "gate_station": bool(gates[2]),
                     "estimated_frames": int(finite.sum())})
        print(f"   -    {str(calibration):22s} {u0 * 1e6:8.2f} {w * 1e6:8.2f}   {held:6.0f}   "
              f"{peak_true * 1e6:9.1f} {peak_est * 1e6:9.1f} {p95 * 1e6:9.2f} {peak_at:6.2f}   "
              f"{'Y' if gates[0] else 'n'}/{'Y' if gates[1] else 'n'}/{'Y' if gates[2] else 'n'}")

    print()
    print("zero-parameter readout from the transfer station (no calibration at all):")
    print("amplitude   s* (m)    z_est (um)   z_true at s* (um)   error (um)")
    transfer = []
    for amplitude in AMPLITUDES_UM:
        run = runs[amplitude]
        readout = transfer_station_readout(run, gaps[amplitude])
        truth_at = float(base._true_bump(np.array([readout["station_m"]]), amplitude * 1e-6)[0])
        error = readout["z_estimate_m"] - truth_at
        transfer.append({"amplitude_um": amplitude, "station_m": readout["station_m"],
                         "z_estimate_m": readout["z_estimate_m"], "z_true_m": truth_at,
                         "error_m": error})
        print(f"{amplitude:9.1f}   {readout['station_m']:7.3f}   {readout['z_estimate_m'] * 1e6:9.1f}   "
              f"{truth_at * 1e6:16.1f}   {error * 1e6:9.1f}")

    passed = all(row["gate_relative"] and row["gate_absolute"] and row["gate_station"] for row in rows)
    verdict = ("a two-parameter map beats the table: every held-out amplitude meets all three gates"
               if passed else
               f"{sum(1 for row in rows if row['gate_absolute'])}/3 held-out amplitudes meet the "
               "absolute gate, none of the folds meets all three")
    print()
    print(f"folds passing all three gates: {sum(1 for r in rows if r['gate_relative'] and r['gate_absolute'] and r['gate_station'])}/3")
    print(f"VERDICT: {verdict}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "parametric.json").write_text(json.dumps(
        {"model": "sigma = 0.5*(1 - tanh((u-u0)/w)), u = d - z",
         "gates": {"relative_limit": RELATIVE_LIMIT, "absolute_limit_m": ABSOLUTE_LIMIT_M,
                   "station_limit_m": STATION_LIMIT_M, "floor_m": FLOOR_M,
                   "calibration_share": CALIBRATION_SHARE},
         "rows": rows, "transfer_station": transfer, "verdict": verdict}, indent=1) + chr(10), encoding="utf-8")
    print(f"report -> {OUT / 'parametric.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
