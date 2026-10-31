"""M7 assembly: one light band of the running surface, reconstructed and judged.

Rounds 251-259 built the pieces.  The split share sigma(s) = blade/(stock+blade) is the quantity that
carries the surface amplitude (round 250: the axle-box acceleration stops being monotone once the
stock unloads, while the split keeps rising); the width-resolved split law turns sigma into a gap
(round 256); and round 259 measured how far sideways a feature can be seen at all: 4 mm, not the
16 mm strip-search window.

This script assembles them into one band reconstruction on the four runs that already exist (the
canonical case with no bump, and the same case with a 50/100/200 um Gaussian bump at 58.5 m, sigma
1.2 m) and reports the answer against gates written into the task book before any of it was run:

    G-ABS   p95(|z_hat - z|) <= 22 um where the truth is real
    G-REL   |z_hat - z| / max(|z|, y_ref) <= 2 %  (98 %), y_ref = 500 um, worst 2 mm bin
    G-LOC   |peak station - the truth's peak| <= 0.20 m
    G-NULL  on the un-bumped run the raw inversion must stay at the background: p95 <= 16.7 um

Two decisions are made explicit because they change the number:

1. **The null run defines the zero.**  The absolute inversion z = d(s) - u carries a constant and
   station-dependent bias, because the split law was measured on a seated model whose wheel already
   penetrates by the static 63.70 um, while d(s) is a pure geometric gap.  G-NULL measures that bias.
   The reconstruction reported here is therefore differential -- z_hat(s) = z_run(s) - z_null(s) -- and
   both the raw and the differential numbers are printed, so the bias cannot hide.
2. **The truth is the synthetic bump this repository injected.**  That makes this an estimator test
   (evidence class B), not a measurement of a real rail.

Coverage is reported next to accuracy: one pass reconstructs a ~4 mm strip of the 37.15 mm head
(11 %), while the contact itself is 16 mm wide (43 %).  Round 259 put the nine-pass design at 100 um.

Writes ``reports/load_split_inversion_2026-10-31/m7_assembly.json``.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s113_profile_inversion as base  # noqa: E402
import s119_width_aware_inversion as law  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "m7_assembly.json"

BASELINE_ROUTE = "straight_one_set"
ABSOLUTE_LIMIT_UM = 22.0
RELATIVE_LIMIT_PCT = 2.0
Y_REF_UM = 500.0
STATION_LIMIT_M = 0.20
WINDOW_FRACTION = base.WINDOW_FRACTION
BIN_M = 0.002
SMOOTH_M = 0.30

CONTACT_BAND_MM = 16.0
IDENTIFIABLE_BAND_MM = 4.0
HEAD_WIDTH_MM = 37.15
NULL_LIMIT_UM = 16.7

# The median-filter window is chosen on the un-bumped run only, so the choice cannot lean on the truth:
# the window that leaves the smallest background is the one the estimator is quietest at.  Ties go to
# the wider window (fewer degrees of freedom spent on noise).
SMOOTH_CANDIDATES = (0.10, 0.20, 0.30, 0.50, 0.80, 1.20)


def build_law():
    """(half_gap_of, invert) from the measured anchors, inverting the measured curve directly."""
    curves, _ = law._measured_curves()
    table_s, table_w = law._width_table()
    anchors = []
    for station in sorted(curves):
        u, sigma = curves[station]
        width = float(law._width_at(np.asarray([station]), table_s, table_w)[0])
        anchors.append((width, law._half_gap(u, sigma), station))
    anchors.sort()
    base_width, base_gap, base_station = min(
        anchors, key=lambda item: abs(item[0] - law.MEASURED_WIDTHS[0]))
    curve_u, curve_sigma = curves[base_station]
    anchor_widths = np.asarray([item[0] for item in anchors], dtype=float)
    anchor_gaps = np.asarray([item[1] for item in anchors], dtype=float)

    def half_gap_of(width_mm: float) -> float:
        return float(np.interp(width_mm, anchor_widths, anchor_gaps,
                               left=float(anchor_gaps[0]), right=float(anchor_gaps[-1])))

    # Invert the measured curve itself.  Searching a u grid and re-sorting by sigma is fragile at the
    # clamped ends: the first version of this script did that and came out monotone the wrong way
    # (higher sigma -> larger gap, and sigma = 1 landing on the clamp), which turned every bump into a
    # sub-micron negative deflection.  Read the shift off the flipped measured curve instead.
    order = np.argsort(curve_sigma)
    sigma_sorted, shift_sorted = curve_sigma[order], curve_u[order]
    keep = np.concatenate(([True], np.diff(sigma_sorted) > 1e-9))
    sigma_inc, shift_inc = sigma_sorted[keep], shift_sorted[keep]

    def invert(sigma: float, g0_um: float) -> float:
        shift = float(np.interp(sigma, sigma_inc, shift_inc))
        return shift + g0_um - base_gap

    return half_gap_of, invert, {"width_mm": base_width, "half_gap_um": base_gap,
                                 "station_m": base_station, "sigma_range": [float(sigma_inc[0]),
                                                                           float(sigma_inc[-1])]}


def profile(route: str, half_gap_of, invert, smooth_m: float) -> dict:
    """Absolute inversion of one archived run: (stations, z = d - u, share seen)."""
    run_id = base._run_id(route)
    run = base._load(run_id)
    stations = run["station"]
    sigma = base._smooth(base._split(run), stations, smooth_m)
    gap_um = base._gap_profile(stations) * 1e6
    table_s, table_w = law._width_table()
    widths = law._width_at(stations, table_s, table_w)
    u = np.full_like(sigma, np.nan)
    valid = (np.isfinite(sigma) & (sigma > law.SIGMA_LO) & (sigma < law.SIGMA_HI)
             & np.isfinite(gap_um))
    for index in np.nonzero(valid)[0]:
        u[index] = invert(float(sigma[index]), half_gap_of(float(widths[index])))
    return {"route": route, "run_id": run_id, "stations": stations,
            "z": gap_um - u, "share": sigma, "valid": valid}


def score(hit: dict, truth_amp_um: float, null: dict | None) -> dict:
    stations = hit["stations"]
    truth = base._true_bump(stations, truth_amp_um) if truth_amp_um else np.zeros_like(stations)
    peak = float(np.max(np.abs(truth)))

    z_raw = hit["z"]
    if null is None:
        z_use = z_raw
    else:
        z_use = z_raw - np.interp(stations, null["stations"], null["z"])

    if peak:
        window = np.abs(truth) >= WINDOW_FRACTION * peak
    else:
        window = np.abs(stations - base.CENTRE_M) <= 2.0
    window = window & np.isfinite(z_use) & np.isfinite(truth)

    if not window.any():
        return {"route": hit["route"], "run_id": hit["run_id"], "truth_peak_um": peak,
                "note": "no station where the truth and the inversion are both defined"}

    error = z_use[window] - truth[window]
    p95 = float(np.percentile(np.abs(error), 95.0))
    worst_rel = 0.0
    s_win = stations[window]
    for start in np.arange(s_win.min(), s_win.max(), BIN_M):
        inside = window & (stations >= start) & (stations < start + BIN_M)
        if not inside.any():
            continue
        denominator = max(float(np.max(np.abs(truth[inside]))), Y_REF_UM)
        worst_rel = max(worst_rel, 100.0 * float(np.max(np.abs(z_use[inside] - truth[inside])))
                        / denominator)

    if peak:
        truth_peak_station = float(s_win[int(np.argmax(np.abs(truth[window])))])
        peak_station = float(s_win[int(np.argmax(np.abs(z_use[window])))])
        peak_error = abs(peak_station - truth_peak_station)
        estimated_peak = float(np.max(np.abs(z_use[window])))
    else:
        truth_peak_station = None
        peak_station = None
        peak_error = 0.0
        estimated_peak = float(np.max(np.abs(z_use[window])))

    raw_p95 = float(np.percentile(np.abs(z_raw[window] - truth[window]), 95.0))
    return {
        "route": hit["route"],
        "run_id": hit["run_id"],
        "truth_peak_um": peak,
        "window_station_m": [float(s_win.min()), float(s_win.max())],
        "estimated_peak_um": estimated_peak,
        "peak_station_m": peak_station,
        "truth_peak_station_m": truth_peak_station,
        "peak_error_m": peak_error,
        "p95_um": p95,
        "raw_p95_um": raw_p95,
        "worst_bin_relative_pct": worst_rel,
        "gates": {"G-ABS": p95 <= ABSOLUTE_LIMIT_UM,
                  "G-REL": worst_rel <= RELATIVE_LIMIT_PCT,
                  "G-LOC": peak_error <= STATION_LIMIT_M},
    }


def choose_smoothing(half_gap_of, invert) -> tuple[float, list[tuple[float, float]]]:
    """Pick the median-filter window that leaves the smallest background on the un-bumped run."""
    scores = []
    for window in SMOOTH_CANDIDATES:
        hit = profile(BASELINE_ROUTE, half_gap_of, invert, window)
        scores.append((window, float(score(hit, 0.0, None)["p95_um"])))
    best = min(scores, key=lambda item: (round(item[1], 6), -item[0]))
    return best[0], scores


def main() -> int:
    half_gap_of, invert, anchor = build_law()
    smoothing, smoothing_scores = choose_smoothing(half_gap_of, invert)
    null_hit = profile(BASELINE_ROUTE, half_gap_of, invert, smoothing)
    null_row = score(null_hit, 0.0, None)
    null_ok = bool(null_row["p95_um"] <= NULL_LIMIT_UM)

    rows = []
    for amplitude_um in base.AMPLITUDES_UM:
        hit = profile(f"one_set_bump{amplitude_um:05.1f}um", half_gap_of, invert, smoothing)
        rows.append(score(hit, amplitude_um, null_hit))

    print(f"law anchor: {anchor['width_mm']:.1f} mm at {anchor['station_m']:.1f} m, "
          f"half gap {anchor['half_gap_um']:+.2f} um, sigma span "
          f"{anchor['sigma_range'][0]:.3f}..{anchor['sigma_range'][1]:.3f}")
    print("smoothing chosen on the null run only: "
          + ", ".join(f"{window:.2f} m -> {value:.1f} um" for window, value in smoothing_scores)
          + f"  => {smoothing:.2f} m")
    print()
    print(f"{'amplitude':>10} {'est peak':>9} {'p95 um':>8} {'raw p95':>8} {'worst 2mm %':>12} "
          f"{'peak err m':>11} {'G-ABS':>6} {'G-REL':>6} {'G-LOC':>6}")
    print(f"{'null':>10} {null_row['estimated_peak_um']:9.2f} {null_row['p95_um']:8.2f} "
          f"{null_row['raw_p95_um']:8.2f} {'-':>12} {'-':>11} "
          f"{'PASS' if null_ok else 'FAIL':>6} {'-':>6} {'-':>6}   <- G-NULL")
    for row in rows:
        gates = row["gates"]
        print(f"{row['truth_peak_um']:10.1f} {row['estimated_peak_um']:9.2f} {row['p95_um']:8.2f} "
              f"{row['raw_p95_um']:8.2f} {row['worst_bin_relative_pct']:12.2f} "
              f"{row['peak_error_m']:11.3f} "
              f"{'PASS' if gates['G-ABS'] else 'FAIL':>6} "
              f"{'PASS' if gates['G-REL'] else 'FAIL':>6} "
              f"{'PASS' if gates['G-LOC'] else 'FAIL':>6}")

    passing = sum(1 for row in rows if all(row["gates"].values()))
    best = min(rows, key=lambda row: row["p95_um"])
    verdict = (f"{passing}/{len(rows)} amplitudes pass all three amplitude gates, and G-NULL is "
               f"{'met' if null_ok else 'missed'} at {null_row['p95_um']:.1f} um against a "
               f"{NULL_LIMIT_UM:.1f} um limit.  The best reconstruction is "
               f"{best['truth_peak_um']:.0f} um at p95 {best['p95_um']:.1f} um "
               f"({best['p95_um'] / ABSOLUTE_LIMIT_UM:.1f}x the gate).  One pass reconstructs a "
               f"{IDENTIFIABLE_BAND_MM:.0f} mm strip, {100.0 * IDENTIFIABLE_BAND_MM / HEAD_WIDTH_MM:.0f} % "
               f"of the {HEAD_WIDTH_MM:.2f} mm head.")
    payload = {
        "baseline_route": BASELINE_ROUTE,
        "law_anchor": anchor,
        "smooth_m": smoothing,
        "smoothing_scores": smoothing_scores,
        "null": null_row,
        "null_limit_um": NULL_LIMIT_UM,
        "null_ok": null_ok,
        "amplitudes": rows,
        "relatives": {"y_ref_um": Y_REF_UM, "limit_pct": RELATIVE_LIMIT_PCT, "bin_m": BIN_M},
        "coverage": {"contact_mm": CONTACT_BAND_MM, "identifiable_mm": IDENTIFIABLE_BAND_MM,
                     "head_mm": HEAD_WIDTH_MM},
        "amplitudes_passing_all_gates": passing,
        "verdict": verdict,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print()
    print(verdict)
    print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
