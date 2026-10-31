"""M5 step 7: invert the bump with the split law resolved by the blade's section width.

Round 255 measured the law at three stations and found it does not collapse in height-above-flush
coordinates: the half-load gap moves +97.3 um at a 45 mm section, -16.3 um at 63 mm and -21.0 um at
72.2 mm, i.e. 113 um of shift before it saturates.  Every earlier estimator used a single law keyed on
``u = d - z``, which is why rounds 251-253 could not carry an amplitude across the calibration range.

This script replaces that with ``sigma(u, w)``: the law measured at the 45 mm section, translated along
the gap axis by the width-dependent half-load gap

    sigma(u, w) = sigma_45(u - g0(w) + g0(45 mm))

with ``g0`` from the three measured anchors, linear in width between them and clamped outside.  The clamp
is reported rather than hidden: no law was measured below 45 mm, and the bump window sits at 35-50 mm.

Nothing here is fitted to the bump runs.  The law comes from dedicated static probes (s118), the geometry
``d(s)`` from the canonical case, the widths from the station file names, and the split ``sigma(s)`` from
the archived runs.  So all three amplitudes are hold-outs, including the 50 um that used to be the
calibration fold.

Gates (unchanged since round 251, written before this script was run)
    G-A  inverted peak recovers the applied peak: |e| / max(z, 0.5 mm) <= 2 %
    G-B  p95(|e|) <= 22 um over the window where the truth exceeds 10 % of its peak
    G-C  inverted peak station within 0.20 m of the truth

Writes ``scratch/s119/inversion_width_aware.json``.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s110_lowering_readings as lowering  # noqa: E402
import s113_profile_inversion as base  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "split_law_vs_station.json"
OUT = ROOT.parent / "scratch" / "s119"

HALF = 0.5
SIGMA_LO, SIGMA_HI = 0.05, 0.95
MEASURED_WIDTHS = (45.0, 63.0, 72.2)
RELATIVE_LIMIT_PCT = 2.0
ABSOLUTE_LIMIT_UM = 22.0
STATION_LIMIT_M = 0.20
FLOOR_UM = 500.0
WINDOW_FRACTION = base.WINDOW_FRACTION


def _width_table() -> tuple[np.ndarray, np.ndarray]:
    """(station, width) for the blade body, from the case's own station file names."""
    raw = json.loads(lowering.CASE.read_text(encoding="utf-8"))
    for template in raw["rail_templates"]:
        for body in template.get("bodies") or []:
            if body.get("id") != "blade":
                continue
            stations, widths = [], []
            for station in body["stations"]:
                width = lowering.width_mm_of(station["profile"]["file"])
                if np.isnan(width):
                    continue
                stations.append(float(station["s_m"]))
                widths.append(width)
            if stations:
                return np.asarray(stations), np.asarray(widths)
    raise SystemExit("no blade body with width-bearing stations in the canonical case")


def _width_at(stations: np.ndarray, table_s: np.ndarray, table_w: np.ndarray) -> np.ndarray:
    return np.interp(stations, table_s, table_w,
                     left=float(table_w[0]), right=float(table_w[-1]))


def _measured_curves() -> tuple[dict[float, tuple[np.ndarray, np.ndarray]], list[float]]:
    """station -> (u_um ascending, sigma descending) from the s118 static probes."""
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    by_station: dict[float, list[dict]] = {}
    for row in report["rows"]:
        if row.get("failed"):
            continue
        if row.get("sigma") is None or not np.isfinite(row["sigma"]):
            continue
        by_station.setdefault(float(row["station_m"]), []).append(row)

    table_s, table_w = _width_table()
    curves, widths = {}, []
    for station, rows in sorted(by_station.items()):
        # ``delta_um`` is the gap the probe imposed: positive = the blade sits lower than flush, so
        # the contact sees a wider gap.  That makes delta itself the u coordinate (the sign of the
        # first version was inverted, and it is why every anchor came out mirrored).
        u = np.asarray([float(row["delta_um"]) for row in rows], dtype=float)
        sigma = np.asarray([float(row["sigma"]) for row in rows], dtype=float)
        order = np.argsort(u)
        u, sigma = u[order], sigma[order]
        keep = np.concatenate(([True], np.diff(u) > 1e-9))
        u, sigma = u[keep], sigma[keep]
        if len(u) < 4:
            continue
        curves[station] = (u, sigma)
        widths.append(float(_width_at(np.asarray([station]), table_s, table_w)[0]))
    if len(curves) < 3:
        raise SystemExit(f"need three measured stations, found {len(curves)}")
    return curves, widths


def _half_gap(u: np.ndarray, sigma: np.ndarray) -> float:
    """u at which sigma crosses 0.5, by linear interpolation of the measured curve."""
    for index in range(len(u) - 1):
        a, b = sigma[index], sigma[index + 1]
        if (a - HALF) * (b - HALF) <= 0.0 and a != b:
            weight = (HALF - a) / (b - a)
            return float(u[index] + weight * (u[index + 1] - u[index]))
    return float("nan")


def main() -> int:
    curves, widths = _measured_curves()
    table_s, table_w = _width_table()

    half_gaps = []
    for station in sorted(curves):
        u, sigma = curves[station]
        width = float(_width_at(np.asarray([station]), table_s, table_w)[0])
        half_gaps.append((width, _half_gap(u, sigma), station))
    half_gaps.sort()

    print("measured anchors (width mm, half-load gap um, station m):")
    for width, gap, station in half_gaps:
        print(f"  {width:6.1f} mm   {gap:+8.2f} um   at {station:.2f} m")

    base_width, base_gap, base_station = min(half_gaps, key=lambda item: abs(item[0] - MEASURED_WIDTHS[0]))
    curve_u, curve_sigma = curves[base_station]
    print(f"reference curve: {base_width:.1f} mm at {base_station:.2f} m, half gap {base_gap:+.2f} um")

    anchor_widths = np.asarray([item[0] for item in half_gaps], dtype=float)
    anchor_gaps = np.asarray([item[1] for item in half_gaps], dtype=float)

    def half_gap_of(width_mm: float) -> float:
        return float(np.interp(width_mm, anchor_widths, anchor_gaps,
                               left=float(anchor_gaps[0]), right=float(anchor_gaps[-1])))

    u_grid = np.linspace(-600.0, 900.0, 6001)

    def sigma_of(u_um: float, g0_um: float) -> float:
        return float(np.interp(u_um - g0_um + base_gap, curve_u, curve_sigma, left=1.0, right=0.0))

    def invert(sigma: float, g0_um: float) -> float:
        values = np.asarray([sigma_of(u, g0_um) for u in u_grid])
        order = np.argsort(values)
        values_sorted, u_sorted = values[order], u_grid[order]
        keep = np.concatenate(([True], np.diff(values_sorted) > 1e-12))
        return float(np.interp(sigma, values_sorted[keep], u_sorted[keep],
                               left=float(u_grid[0]), right=float(u_grid[-1])))

    rows, verdicts = [], []
    for amplitude_um in base.AMPLITUDES_UM:
        route = base._run_id(f"one_set_bump{amplitude_um:05.1f}um")
        run = base._load(route)
        stations = run["station"]
        sigma_series = base._smooth(base._split(run), stations, base.SMOOTH_M)
        gap_um = base._gap_profile(stations) * 1e6
        width_series = _width_at(stations, table_s, table_w)

        u = np.full_like(sigma_series, np.nan)
        valid = (np.isfinite(sigma_series) & (sigma_series > SIGMA_LO)
                 & (sigma_series < SIGMA_HI) & np.isfinite(gap_um))
        for index in np.nonzero(valid)[0]:
            u[index] = invert(float(sigma_series[index]), half_gap_of(float(width_series[index])))

        z = gap_um - u
        truth = base._true_bump(stations, amplitude_um * 1e-6) * 1e6
        peak_truth = float(np.nanmax(truth))
        window = np.abs(truth) > WINDOW_FRACTION * peak_truth
        finite = np.isfinite(z) & np.isfinite(truth) & window
        if not np.any(finite):
            rows.append({"amplitude_um": amplitude_um, "route": route, "valid_fraction": 0.0,
                         "gate_a": False, "gate_b": False, "gate_c": False})
            verdicts.append(False)
            continue

        peak_index = int(np.nanargmax(np.where(np.isfinite(z), z, -np.inf)))
        peak_um = float(z[peak_index])
        peak_station = float(stations[peak_index])
        error_um = peak_um - peak_truth
        relative_pct = 100.0 * abs(error_um) / max(peak_truth, FLOOR_UM)
        p95 = float(np.nanpercentile(np.abs(z[finite] - truth[finite]), 95))
        truth_station = float(stations[int(np.nanargmax(truth))])
        station_error = abs(peak_station - truth_station)

        gate_a = relative_pct <= RELATIVE_LIMIT_PCT
        gate_b = p95 <= ABSOLUTE_LIMIT_UM
        gate_c = station_error <= STATION_LIMIT_M
        rows.append({"amplitude_um": amplitude_um, "route": route, "peak_um": peak_um,
                     "peak_station_m": peak_station, "truth_peak_um": peak_truth,
                     "error_um": error_um, "relative_pct": relative_pct, "p95_um": p95,
                     "station_error_m": station_error,
                     "valid_fraction": float(np.count_nonzero(valid) / max(len(valid), 1)),
                     "width_at_peak_mm": float(width_series[peak_index]),
                     "gate_a": bool(gate_a), "gate_b": bool(gate_b), "gate_c": bool(gate_c)})
        verdicts.append(bool(gate_a and gate_b and gate_c))

    print("\n amp    route                              peak_est  peak_true    rel%    p95(um)  at s   w(mm)  gates")
    for row in rows:
        if "peak_um" not in row:
            print(f"{row['amplitude_um']:5.0f}  {row['route']:35s}  no valid frames")
            continue
        gates = f"{'Y' if row['gate_a'] else 'n'}/{'Y' if row['gate_b'] else 'n'}/{'Y' if row['gate_c'] else 'n'}"
        print(f"{row['amplitude_um']:5.0f}  {row['route']:35s}  {row['peak_um']:8.1f}  "
              f"{row['truth_peak_um']:9.1f}  {row['relative_pct']:6.2f}  {row['p95_um']:8.1f}  "
              f"{row['peak_station_m']:5.2f}  {row['width_at_peak_mm']:6.1f}  {gates}")

    narrow = table_w < float(anchor_widths.min())
    payload = {"anchors": [{"width_mm": width, "half_gap_um": gap, "station_m": station}
                           for width, gap, station in half_gaps],
               "reference": {"width_mm": base_width, "station_m": base_station,
                             "half_gap_um": base_gap},
               "extrapolation": {"measured_width_range_mm": [float(anchor_widths.min()),
                                                            float(anchor_widths.max())],
                                 "blade_stations_below_range": int(np.count_nonzero(narrow)),
                                 "blade_stations_total": int(len(table_w)),
                                 "clamped_outside": True},
               "rows": rows,
               "folds_passing_all_three": int(sum(verdicts)),
               "folds_total": len(verdicts),
               "verdict": ("the width-aware law carries the amplitude" if all(verdicts)
                           else "the width-aware law still does not carry the amplitude")}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "inversion_width_aware.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nfolds passing all three gates: {sum(verdicts)}/{len(verdicts)}")
    print(f"VERDICT: {payload['verdict']}")
    print(f"measured widths {anchor_widths.min():.1f}..{anchor_widths.max():.1f} mm; "
          f"blade stations below that range {int(np.count_nonzero(narrow))}/{len(table_w)} (clamped)")
    print(f"data -> {OUT / 'inversion_width_aware.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
