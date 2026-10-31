"""M7 step 3: hold out an amplitude and a position the estimators were never calibrated on.

Rounds 260/261 both scored themselves on the same runs that tuned them.  The share-only forward fit of
round 261 passes 5/9 there and fails at or above 100 um, where the share saturates; the onset-station
table of round 257 was itself built on 20/30/40/50/60/80/100/120/200 um at centre 58.5 m, so quoting it
for those runs is fitting the calibration set.

This script therefore holds out both axes:

    H-A  150 um at centre 58.5 m   -- an amplitude that is in neither calibration (the fit series has
                                      120 and 200; the onset table has 120 and 200, so 150 is an
                                      interpolation of that table, not a repetition of its vertices)
    H-B  100 um at centre 59.5 m   -- a position 1 m away from every calibration run

Pre-registered before either case was built (identical to rounds 260/261):

    G-ABS  p95(|z_hat - z|) <= 22 um over the window where the truth exceeds 10 % of its peak
    G-REL  worst 2 mm bin |e| / max(|z|, 500 um) <= 2 %
    G-LOC  |peak station - the truth's peak| <= 0.20 m

Two estimators are scored on each hold-out, because round 261 showed they carry different information:

    share-only   the two-parameter forward fit (amplitude, centre) of round 261
    hybrid       amplitude from the *onset station* through the round-257 linear map
                 A = (58.610 m - onset) / 3.2699 mm/um, centre from the share fit with A held

The onset map is a property of the ramp plus the amplitude and does not follow the bump (round 258
measured 67 mm of onset movement for a 1 m shift of the bump), so it is allowed to set the amplitude
only, never the position.

Writes ``reports/load_split_inversion_2026-10-31/holdout.json``.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s113_profile_inversion as base  # noqa: E402
import s123_m7_assembly as assembly  # noqa: E402
import s124_joint_inversion as fitter  # noqa: E402

OUT = ROOT.parent / "scratch" / "s125"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "holdout.json"
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"

SPEED_KMH = 80.0
DURATION_S = 0.6
SIGMA_M = base.SIGMA_M
ONSET_SHARE = 0.95
ONSET_OFFSET_M = 58.610
ONSET_SLOPE_MM_PER_UM = 3.2699

# (label, amplitude um, centre m)
HOLDOUTS = (("h-a-150um-c58.5", 150.0, 58.5), ("h-b-100um-c59.5", 100.0, 59.5))


def route_of(label: str) -> str:
    """s99 labels an explicit case by its file stem, so this must be the stem, not a tidy alias."""
    return label


def build() -> None:
    source = json.loads(CASE.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    variants = []
    for label, amplitude_um, centre_m in HOLDOUTS:
        case = json.loads(json.dumps(source))
        case["case_id"] = f"{source['case_id']}_{label.replace('-', '_')}"
        case["purpose_detail"] = (
            f"M7 hold-out variant: {label}, a Gaussian bump of {amplitude_um:.1f} um at "
            f"{centre_m:.2f} m, sigma {SIGMA_M:.2f} m, on the blade body only")
        touched = 0
        for template in case["rail_templates"]:
            for body in template.get("bodies") or []:
                if body.get("id") != "blade":
                    continue
                for station in body["stations"]:
                    weight = float(np.exp(-0.5 * ((float(station["s_m"]) - centre_m) / SIGMA_M) ** 2))
                    if weight < 1e-3:
                        continue
                    station["profile"]["z_offset_m"] = float(
                        station["profile"].get("z_offset_m", 0.0)) + amplitude_um * 1e-6 * weight
                    touched += 1
        path = OUT / f"{label}.json"
        path.write_text(json.dumps(case, indent=1, ensure_ascii=False) + chr(10), encoding="utf-8")
        variants.append({"label": label, "route": route_of(label), "amplitude_um": amplitude_um,
                         "centre_m": centre_m, "path": str(path), "stations_touched": touched})
        print(f"{label}: {touched} blade stations, {path}")
    (OUT / "variants.json").write_text(json.dumps(variants, indent=2) + chr(10), encoding="utf-8")


def run() -> int:
    variants = json.loads((OUT / "variants.json").read_text(encoding="utf-8"))
    for variant in variants:
        command = [sys.executable, "-X", "utf8", str(ROOT / "scripts" / "s99_run_archive.py"),
                   "--case", variant["path"], "--speed-kmh", str(SPEED_KMH),
                   "--duration", str(DURATION_S), "--note", "campaign=m7-holdout",
                   "--note", f"amplitude_um={variant['amplitude_um']}",
                   "--note", f"centre_m={variant['centre_m']}"]
        print("+", " ".join(command[-9:]))
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        sys.stdout.write(completed.stdout[-400:])
        sys.stderr.write(completed.stderr[-400:])
        if completed.returncode != 0:
            return completed.returncode
    return 0


def _onset_station(stations: np.ndarray, share: np.ndarray) -> float:
    """First station where the share reaches ONSET_SHARE (round 257's definition)."""
    above = np.nonzero(np.isfinite(share) & (share >= ONSET_SHARE))[0]
    return float(stations[above[0]]) if len(above) else float("nan")


def _score(z_hat: np.ndarray, stations: np.ndarray, truth_um: float, centre_m: float) -> dict:
    truth = truth_um * np.exp(-0.5 * ((stations - centre_m) / SIGMA_M) ** 2)
    peak = float(np.max(np.abs(truth)))
    window = np.abs(truth) >= assembly.WINDOW_FRACTION * peak
    error = z_hat[window] - truth[window]
    p95 = float(np.percentile(np.abs(error), 95.0))
    worst_rel = 0.0
    s_win = stations[window]
    for start in np.arange(s_win.min(), s_win.max(), assembly.BIN_M):
        inside = window & (stations >= start) & (stations < start + assembly.BIN_M)
        if not inside.any():
            continue
        denominator = max(float(np.max(np.abs(truth[inside]))), assembly.Y_REF_UM)
        worst_rel = max(worst_rel, 100.0 * float(np.max(np.abs(z_hat[inside] - truth[inside])))
                        / denominator)
    peak_station = float(s_win[int(np.argmax(np.abs(z_hat[window])))])
    truth_station = float(s_win[int(np.argmax(np.abs(truth[window])))])
    return {"amplitude_relative_pct": 100.0 * abs(float(np.max(np.abs(z_hat[window]))) - truth_um)
            / max(truth_um, assembly.Y_REF_UM),
            "p95_um": p95, "worst_bin_relative_pct": worst_rel,
            "peak_error_m": abs(peak_station - truth_station),
            "gates": {"G-ABS": p95 <= assembly.ABSOLUTE_LIMIT_UM,
                      "G-REL": worst_rel <= assembly.RELATIVE_LIMIT_PCT,
                      "G-LOC": abs(peak_station - truth_station) <= assembly.STATION_LIMIT_M}}


def report() -> int:
    build_law_result = assembly.build_law()
    sigma_of = fitter.share_law(build_law_result)
    _, invert, _ = build_law_result
    half_gap_of = build_law_result[0]

    null_run = base._load(base._run_id(assembly.BASELINE_ROUTE))
    null_stations = null_run["station"]
    null_share = base._smooth(base._split(null_run), null_stations, base.SMOOTH_M)
    null_widths = fitter.law._width_at(null_stations, *fitter.law._width_table())
    null_u0 = np.full_like(null_share, np.nan)
    ok = np.isfinite(null_share) & (null_share > fitter.SHARE_LO) & (null_share < fitter.SHARE_HI)
    for index in np.nonzero(ok)[0]:
        null_u0[index] = invert(float(null_share[index]), half_gap_of(float(null_widths[index])))
    null_state = {"stations": null_stations, "share_raw": null_share, "u0": null_u0}

    rows = []
    for label, amplitude_um, centre_m in HOLDOUTS:
        route = route_of(label)
        share_fit = fitter.fit_one(route, sigma_of, null_state)
        stations = share_fit["stations"]
        run = base._load(base._run_id(route))
        share = base._smooth(base._split(run), stations, base.SMOOTH_M)
        onset = _onset_station(stations, share)
        onset_amplitude = ((ONSET_OFFSET_M - onset) * 1000.0 / ONSET_SLOPE_MM_PER_UM
                           if np.isfinite(onset) else float("nan"))

        share_z = (share_fit["amplitude_um"] * np.exp(
            -0.5 * ((stations - share_fit["centre_m"]) / SIGMA_M) ** 2))
        hybrid_amplitude = onset_amplitude if np.isfinite(onset_amplitude) else share_fit["amplitude_um"]
        hybrid_centre = share_fit["centre_m"]
        hybrid_z = hybrid_amplitude * np.exp(-0.5 * ((stations - hybrid_centre) / SIGMA_M) ** 2)

        rows.append({
            "label": label, "truth_amplitude_um": amplitude_um, "truth_centre_m": centre_m,
            "share_only": {"amplitude_um": share_fit["amplitude_um"],
                           "centre_m": share_fit["centre_m"],
                           **_score(share_z, stations, amplitude_um, centre_m)},
            "hybrid": {"amplitude_um": float(hybrid_amplitude),
                       "onset_station_m": onset,
                       "centre_m": hybrid_centre,
                       **_score(hybrid_z, stations, amplitude_um, centre_m)},
        })

    print(f"{'hold-out':16} {'est':>8} {'p95':>8} {'worst %':>8} {'loc err':>8}  gates")
    for row in rows:
        for name in ("share_only", "hybrid"):
            block = row[name]
            gates = block["gates"]
            print(f"{row['label']:16} {block['amplitude_um']:8.1f} {block['p95_um']:8.2f} "
                  f"{block['worst_bin_relative_pct']:8.2f} {block['peak_error_m']:8.3f}  "
                  f"{'PASS' if gates['G-ABS'] else 'FAIL'}/"
                  f"{'PASS' if gates['G-REL'] else 'FAIL'}/"
                  f"{'PASS' if gates['G-LOC'] else 'FAIL'}   ({name})")

    share_passes = sum(1 for row in rows if all(row["share_only"]["gates"].values()))
    hybrid_passes = sum(1 for row in rows if all(row["hybrid"]["gates"].values()))
    verdict = (f"share-only {share_passes}/{len(rows)}, hybrid {hybrid_passes}/{len(rows)} on the two "
               f"hold-outs; the calibration series of round 261 gave 5/9 with the share-only estimator")
    print()
    print(verdict)
    payload = {"holdouts": rows, "onset_map": {"offset_m": ONSET_OFFSET_M,
                                               "slope_mm_per_um": ONSET_SLOPE_MM_PER_UM},
               "share_only_passes": share_passes, "hybrid_passes": hybrid_passes,
               "verdict": verdict}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + chr(10), encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0


def main(argv: list[str]) -> int:
    if "--build" in argv:
        build()
    if "--run" in argv:
        return run()
    if "--report" in argv:
        return report()
    print("use --build, --run or --report")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
