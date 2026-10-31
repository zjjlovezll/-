"""M8 step 1: two peaks instead of one -- does the forward fit still find a profile?

Round 261 fitted one bump; rounds 271-272 carried that across the head and joined two passes.  A
corrugated surface is not one bump, so the first question M8 has to answer is whether the same forward
fit, given the *number* of peaks but not their positions or amplitudes, recovers a profile that the
gates can still judge.

Structure of the test (pre-registered before the run):

    z(s) = A1 exp(-0.5((s - s1)/W)^2) + A2 exp(-0.5((s - s2)/W)^2),   W = 0.35 m (declared prior)

    G-ABS   p95(|z_hat - z|) <= 22 um where the truth exceeds 10 % of its peak
    G-LOC   |s_i - truth_i| <= 0.20 m for **each** peak
    G-AMP   |A_i - truth_i| / max(truth_i, 500 um) <= 2 % for each peak
    G-SEP   the two fitted centres stay apart by >= 0.5 m, i.e. the peaks are not merged

Two peaks, 1.8 m apart with a 0.35 m width, so they are separated by about five widths: a merge would
be the fit's own failure, not a resolution limit.

The geometry, the law, the null-calibrated operating point and the gates all come from rounds 261/271;
only the number of peaks changes, and it is declared.
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

CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s130"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "two_peak_fit.json"

ROUTE = "one_set_twopeak"
PEAKS = ((57.6, 50.0), (59.4, 30.0))          # (centre m, amplitude um) -- fixed before the run
WIDTH_M = 0.35
SPEED_KMH = base.SPEED_KMH
DURATION_S = base.DURATION_S
FIT_LO_M, FIT_HI_M = joint.FIT_LO_M, joint.FIT_HI_M
SHARE_LO, SHARE_HI = joint.SHARE_LO, joint.SHARE_HI
ABSOLUTE_LIMIT_UM = assembly.ABSOLUTE_LIMIT_UM
RELATIVE_LIMIT_PCT = joint.RELATIVE_LIMIT_PCT
STATION_LIMIT_M = assembly.STATION_LIMIT_M
Y_REF_UM = assembly.Y_REF_UM
WINDOW_FRACTION = assembly.WINDOW_FRACTION
BIN_M = assembly.BIN_M
MIN_SEPARATION_M = 0.5


def truth_profile(stations: np.ndarray) -> np.ndarray:
    total = np.zeros_like(stations)
    for centre, amplitude in PEAKS:
        total += amplitude * np.exp(-0.5 * ((stations - centre) / WIDTH_M) ** 2)
    return total


def model(params: np.ndarray, stations: np.ndarray) -> np.ndarray:
    peak_a, centre_a, peak_b, centre_b = params
    return (peak_a * np.exp(-0.5 * ((stations - centre_a) / WIDTH_M) ** 2)
            + peak_b * np.exp(-0.5 * ((stations - centre_b) / WIDTH_M) ** 2))


def build() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    case = json.loads(CASE.read_text(encoding="utf-8"))
    rail = case["rail_templates"][1]
    touched = 0
    for body in rail.get("bodies") or []:
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
                             f" | two-peak corrugation variant: {PEAKS} um, width {WIDTH_M} m")
    path = OUT / f"{ROUTE}.json"
    path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    print(f"two peaks {PEAKS} um at width {WIDTH_M} m -> {path.name} ({touched} blade stations)")
    return 0


def _null_state() -> dict:
    build_law_result = assembly.build_law()
    _, invert, _ = build_law_result
    half_gap_of = build_law_result[0]
    null_run = base._load(base._run_id(assembly.BASELINE_ROUTE))
    stations = null_run["station"]
    share = base._smooth(base._split(null_run), stations, base.SMOOTH_M)
    widths = law._width_at(stations, *law._width_table())
    u0 = np.full_like(share, np.nan)
    usable = np.isfinite(share) & (share > SHARE_LO) & (share < SHARE_HI)
    for index in np.nonzero(usable)[0]:
        u0[index] = invert(float(share[index]), half_gap_of(float(widths[index])))
    return {"stations": stations, "u0": u0}


def report() -> int:
    build_law_result = assembly.build_law()
    sigma_of = joint.share_law(build_law_result)
    null_state = _null_state()

    run = base._load(base._run_id(ROUTE))
    stations = np.asarray(run["station"], dtype=float)
    observed = base._smooth(base._split(run), stations, base.SMOOTH_M)
    widths = law._width_at(stations, *law._width_table())
    u0 = null_state["u0"]

    usable = (np.isfinite(observed) & np.isfinite(u0) & (stations >= FIT_LO_M) & (stations <= FIT_HI_M)
              & (observed >= SHARE_LO) & (observed <= SHARE_HI))

    def residual(params: np.ndarray) -> np.ndarray:
        predicted = sigma_of(u0[usable] + model(params, stations[usable]), widths[usable])
        return predicted - observed[usable]

    starts = []
    for shift_a in (-0.6, 0.0, 0.6):
        for shift_b in (-0.6, 0.0, 0.6):
            starts.append([40.0, PEAKS[0][0] + shift_a, 40.0, PEAKS[1][0] + shift_b])

    best = None
    for start in starts:
        solved = least_squares(residual, np.asarray(start, dtype=float),
                               bounds=([1.0, FIT_LO_M, 1.0, FIT_LO_M], [400.0, FIT_HI_M, 400.0, FIT_HI_M]),
                               method="trf", xtol=1e-12, ftol=1e-12)
        cost = float(np.sum(solved.fun ** 2))
        if best is None or cost < best[0]:
            best = (cost, solved)
    cost, solved = best
    params = [float(value) for value in solved.x]
    fitted = model(solved.x, stations)
    truth = truth_profile(stations)

    peak = float(np.max(np.abs(truth)))
    window = np.abs(truth) >= WINDOW_FRACTION * peak
    error = fitted[window] - truth[window]
    p95 = float(np.percentile(np.abs(error), 95.0))

    worst_bin = 0.0
    start_s = float(stations[window].min())
    for edge in np.arange(start_s, float(stations[window].max()), BIN_M):
        inside = window & (stations >= edge) & (stations < edge + BIN_M)
        if not inside.any():
            continue
        denominator = max(float(np.max(np.abs(truth[inside]))), Y_REF_UM)
        worst_bin = max(worst_bin, 100.0 * float(np.max(np.abs(fitted[inside] - truth[inside]))) / denominator)

    found = sorted([(params[1], params[0]), (params[3], params[2])])
    wanted = sorted([(centre, amplitude) for centre, amplitude in PEAKS])
    per_peak = []
    for (centre_hat, amplitude_hat), (centre_true, amplitude_true) in zip(found, wanted):
        per_peak.append({"centre_true_m": centre_true, "centre_fit_m": centre_hat,
                         "location_error_m": abs(centre_hat - centre_true),
                         "amplitude_true_um": amplitude_true, "amplitude_fit_um": amplitude_hat,
                         "amplitude_relative_pct": 100.0 * abs(amplitude_hat - amplitude_true)
                         / max(amplitude_true, Y_REF_UM)})
    separation = abs(params[1] - params[3])

    gates = {"G-ABS": p95 <= ABSOLUTE_LIMIT_UM,
             "G-LOC": all(row["location_error_m"] <= STATION_LIMIT_M for row in per_peak),
             "G-AMP": all(row["amplitude_relative_pct"] <= RELATIVE_LIMIT_PCT for row in per_peak),
             "G-SEP": separation >= MIN_SEPARATION_M}

    print(f"run {base._run_id(ROUTE)}  stations {stations.size}  usable {int(usable.sum())}  cost {cost:.4e}")
    print(f"{'peak':>4} {'s_true':>8} {'s_fit':>8} {'d s m':>7} {'A_true':>7} {'A_fit':>7} {'rel %':>7}")
    for index, row in enumerate(per_peak, start=1):
        print(f"{index:>4} {row['centre_true_m']:8.3f} {row['centre_fit_m']:8.3f} "
              f"{row['location_error_m']:7.3f} {row['amplitude_true_um']:7.1f} "
              f"{row['amplitude_fit_um']:7.1f} {row['amplitude_relative_pct']:7.2f}")
    print(f"\np95 {p95:.2f} um (gate {ABSOLUTE_LIMIT_UM:.0f})   worst 2 mm bin {worst_bin:.2f} % "
          f"(gate {RELATIVE_LIMIT_PCT:.1f})   separation {separation:.3f} m (gate {MIN_SEPARATION_M:.1f})")
    print("/".join(f"{name}: {'PASS' if ok else 'FAIL'}" for name, ok in gates.items()))
    verdict = ("both peaks are recovered and the profile clears the absolute gate"
               if all(gates.values()) else
               "at least one gate fails; the two-peak profile is not recovered as such")
    print(f"VERDICT: {verdict}")

    payload = {"route": ROUTE, "run_id": base._run_id(ROUTE), "peaks_true": PEAKS,
               "width_m_prior": WIDTH_M, "fit_window_m": [FIT_LO_M, FIT_HI_M],
               "params": {"amplitude_a": params[0], "centre_a": params[1],
                          "amplitude_b": params[2], "centre_b": params[3]},
               "per_peak": per_peak, "separation_m": separation, "p95_um": p95,
               "worst_bin_relative_pct": worst_bin, "gates": gates, "verdict": verdict,
               "starts": len(starts)}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0


def main(argv: list[str]) -> int:
    if "--build" in argv:
        return build()
    if "--report" in argv:
        return report()
    raise SystemExit("use --build or --report")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
