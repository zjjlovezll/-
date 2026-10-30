"""M5 step 4: put the contact model inside the inversion, so the stock-unloading branch is represented.

Round 252 showed that no map ``sigma = f(u)`` can work once the bump starts unloading the stock, because
the gap at which the load halves moves with the amplitude.  The fix is not a better one-dimensional map;
it is a forward model of the split that contains the branch, inverted by root finding.

Model
-----
Both bodies of the rail carry the axle load ``N`` (measured per frame) through strip contacts, each obeying

    F = C * max(0, penetration) ** 1.5

with one stiffness per body (``C_stock``, ``C_blade`` -- two parameters for the whole dataset).  The wheel
sits at one height, so with ``g = d(s) - z(s)`` (positive = the blade is lower than the stock):

    stock_pen  = p - max(0, -g)      blade_pen = p - max(0, g)
    F_stock + F_blade = N            ->  solve p by bisection
    sigma_pred(g, N) = F_blade / N

That is the branch: when ``g`` is negative enough, ``stock_pen`` clips at zero and the stock leaves the
picture entirely, which is exactly what round 250 measured.

Inversion
---------
For each frame, find the ``g`` that reproduces the measured ``sigma`` (bisection on a monotone function),
then ``z = d - g``.  Nothing is tabulated, so the model extends to any amplitude.

Calibration protocol (leave-one-out, unchanged from round 252)
--------------------------------------------------------------
Fit ``(C_stock, C_blade)`` on the two amplitudes a fold is allowed to see, apply to the third.  Gates:

    G-A  |peak_est - peak_true| / max(peak_true, 0.5 mm) <= 2 %
    G-B  p95(|e|) <= 22 um over frames where the truth exceeds 10 % of its peak
    G-C  the station of the inverted peak is within 0.20 m of 58.5 m
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
from scipy.optimize import brentq, least_squares

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s113_profile_inversion as base  # noqa: E402

OUT = ROOT.parent / "scratch" / "s115"
CENTRE_M = base.CENTRE_M
AMPLITUDES_UM = base.AMPLITUDES_UM
RELATIVE_LIMIT = base.RELATIVE_LIMIT
ABSOLUTE_LIMIT_M = base.ABSOLUTE_LIMIT_M
STATION_LIMIT_M = base.STATION_LIMIT_M
WINDOW_FRACTION = base.WINDOW_FRACTION
FLOOR_M = base.FLOOR_M

# The frozen contact stiffness is 1.1267e11 N/m^1.5, so the two bodies are expected within a factor of a
# few of that; the bounds are wide enough to let the data speak and narrow enough to keep the fit sane.
C_LOW, C_HIGH = 2.0e10, 6.0e11


def _penetrations(p: float, g: float) -> tuple[float, float]:
    return p - max(0.0, -g), p - max(0.0, g)


def _sigma(g: float, normal: float, c_stock: float, c_blade: float) -> float:
    def net(p: float) -> float:
        stock_pen, blade_pen = _penetrations(p, g)
        return (c_stock * max(0.0, stock_pen) ** 1.5
                + c_blade * max(0.0, blade_pen) ** 1.5 - normal)

    try:
        p = brentq(net, 0.0, 3.0e-3, xtol=1e-12, rtol=1e-12, maxiter=200)
    except ValueError:
        return float("nan")
    stock_pen, blade_pen = _penetrations(p, g)
    blade = c_blade * max(0.0, blade_pen) ** 1.5
    total = blade + c_stock * max(0.0, stock_pen) ** 1.5
    return float(blade / total) if total > 0 else float("nan")


def _fit(samples: list[tuple[np.ndarray, np.ndarray, np.ndarray]]) -> tuple[float, float]:
    def residual(parameters: np.ndarray) -> np.ndarray:
        c_stock, c_blade = parameters
        pieces = []
        for g, normal, sigma in samples:
            predicted = np.asarray([_sigma(float(gv), float(nv), c_stock, c_blade)
                                    for gv, nv in zip(g, normal)])
            pieces.append(np.nan_to_num(predicted - sigma, nan=1.0))
        return np.concatenate(pieces)

    start = np.array([1.1e11, 1.1e11])
    solution = least_squares(residual, start, bounds=([C_LOW, C_LOW], [C_HIGH, C_HIGH]),
                             xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=400)
    return float(solution.x[0]), float(solution.x[1])


def _invert(sigma: np.ndarray, normal: np.ndarray, c_stock: float,
            c_blade: float) -> np.ndarray:
    out = np.full(sigma.shape, np.nan)
    low, high = -4.0e-4, 4.0e-4
    for index, (target, load) in enumerate(zip(sigma, normal)):
        if not (np.isfinite(target) and np.isfinite(load) and load > 1e3):
            continue
        if not (0.0 < target < 1.0):
            continue
        try:
            out[index] = brentq(lambda g: _sigma(g, load, c_stock, c_blade) - target,
                                low, high, xtol=1e-10, rtol=1e-12, maxiter=200)
        except ValueError:
            continue
    return out


def main() -> int:
    runs, gaps, normals = {}, {}, {}
    for amplitude in AMPLITUDES_UM:
        run = base._load(base._run_id(f"one_set_bump{amplitude:05.1f}um"))
        runs[amplitude] = run
        gaps[amplitude] = base._gap_profile(run["station"])
        normals[amplitude] = run["stock"] + run["blade"]
        print(f"{amplitude:6.1f} um  frames {run['station'].size}  "
              f"N {np.nanmedian(normals[amplitude]) / 1e3:.2f} kN")
    print()

    def samples_for(amplitudes: tuple[float, ...]) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
        out = []
        for amplitude in amplitudes:
            run = runs[amplitude]
            g = gaps[amplitude] - base._true_bump(run["station"], amplitude * 1e-6)
            sigma = base._smooth(base._split(run), run["station"], base.SMOOTH_M)
            keep = np.isfinite(g) & np.isfinite(sigma) & np.isfinite(normals[amplitude])
            out.append((g[keep], normals[amplitude][keep], sigma[keep]))
        return out

    print("fold   calibration      C_stock (N/m^1.5)  C_blade  held out  peak_true  peak_est  p95 (um)  at s   gates")
    rows = []
    for held in AMPLITUDES_UM:
        calibration = tuple(amplitude for amplitude in AMPLITUDES_UM if amplitude != held)
        c_stock, c_blade = _fit(samples_for(calibration))
        run = runs[held]
        sigma = base._smooth(base._split(run), run["station"], base.SMOOTH_M)
        g_est = _invert(sigma, normals[held], c_stock, c_blade)
        truth = base._true_bump(run["station"], held * 1e-6)
        estimate = gaps[held] - g_est
        finite = np.isfinite(estimate) & np.isfinite(truth) & ~np.isnan(gaps[held])
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
                     "c_stock": c_stock, "c_blade": c_blade, "peak_true_m": peak_true,
                     "peak_estimate_m": peak_est, "relative_error": relative, "p95_error_m": p95,
                     "peak_station_m": peak_at, "gate_relative": bool(gates[0]),
                     "gate_absolute": bool(gates[1]), "gate_station": bool(gates[2]),
                     "estimated_frames": int(finite.sum())})
        print(f"   -    {str(calibration):18s} {c_stock:15.4g}  {c_blade:9.4g}  {held:6.0f}  "
              f"{peak_true * 1e6:9.1f} {peak_est * 1e6:9.1f} {p95 * 1e6:9.2f} {peak_at:6.2f}   "
              f"{'Y' if gates[0] else 'n'}/{'Y' if gates[1] else 'n'}/{'Y' if gates[2] else 'n'}")

    passed = sum(1 for row in rows if row["gate_relative"] and row["gate_absolute"] and row["gate_station"])
    verdict = (f"the model-based inversion passes all three gates on {passed}/3 held-out amplitudes")
    print()
    print(f"folds passing all three gates: {passed}/3")
    print(f"frozen contact stiffness for reference: 1.1267e11 N/m^1.5")
    print(f"VERDICT: {verdict}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "model.json").write_text(json.dumps(
        {"model": "F = C*max(0,p)^1.5 per body, common wheel height, stock clips at zero",
         "frozen_c": 1.1267e11,
         "gates": {"relative_limit": RELATIVE_LIMIT, "absolute_limit_m": ABSOLUTE_LIMIT_M,
                   "station_limit_m": STATION_LIMIT_M, "floor_m": FLOOR_M},
         "rows": rows, "verdict": verdict}, indent=1) + chr(10), encoding="utf-8")
    print(f"report -> {OUT / 'model.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
