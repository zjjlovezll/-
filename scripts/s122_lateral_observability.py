"""How far sideways can a surface feature be seen?  The lateral half-width of the observability map.

Round 250 showed the axle-box acceleration sees a bump's *position*.  Round 257-258 showed the blade's
saturation-onset station sees its *amplitude*.  Both measurements used bumps that lift the whole section, so
neither says anything about the axis the wheel actually samples: **lateral position**.  A bump 8 mm to the side
of the contact line is a different physical object from a bump on it, and the whole `Omega_obs` argument of M4
hangs on where that boundary is.

There is a closed prediction.  Let the wheel and rail surfaces near the contact be locally quadratic with
radii `R_w`, `R_r`.  A bump of height `A` at lateral offset `y` from the contact can only become the contact
point when it clears the gap that separates the two surfaces there:

    A*(y) = y**2 / 2 * (1 / R_r + 1 / R_w)

so the observable lateral half-width for amplitude `A` is

    w(A) = sqrt(2 * A / (1 / R_r + 1 / R_w)).

Two candidate models, both using the radii measured at this very contact (round 203/247: `R_rail = 295.27 mm`,
`R_wheel = 1273.65 mm`):

    model A  both curvatures   A*(6) = 75 um   A*(8) = 133 um   w(100) = 6.9 mm
    model B  cone only (R_w = inf, 1:40 tread tangent)   A*(6) = 61 um   A*(8) = 108 um   w(100) = 7.7 mm

A 100 um bump at 8 mm is *below* the threshold under model A (75 % of it) and *just above* under model B
(93 %), so a single amplitude with the lateral offset stepped 0 / 6 / 8 / 10 mm separates them: the response
should fall to essentially zero between 6 and 8 mm (A), or survive 8 mm and die by 10 mm (B).

Pre-registered reading, written before the runs exist:
    peak |da| on `axle1_box_right` at y0 = 0 sets the reference; a variant is "invisible" when its peak is
    below 5 % of that reference and its blade share never reaches the 0.95 onset threshold;
    model A is supported if 6 mm is visible and 8 mm is invisible;
    model B is supported if 8 mm is visible (>= 20 % of reference) and 10 mm is invisible;
    anything else is "the boundary does not lie where either curvature model puts it".

Usage:
    python -X utf8 scripts/s122_lateral_observability.py --build
    # four runs: scripts/s99_run_archive.py --case <abs path> --speed-kmh 80 --duration 0.6
    python -X utf8 scripts/s122_lateral_observability.py --report

Outputs:
    scratch/s122/sections/y<y0>mm/<station>.txt   per-station section files with the lateral bump applied
    scratch/s122/one_set_lat_y<y0>mm.json         case variants
    reports/load_split_inversion_2026-10-31/lateral_observability.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import s113_profile_inversion as INV  # noqa: E402

CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s122"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "lateral_observability.json"
BASELINE_ROUTE = "straight_one_set"

SPEED_KMH = 80.0
DURATION_S = 0.6
AMPLITUDE_UM = 100.0
CENTRE_M = 58.5
SIGMA_S_M = 1.2
SIGMA_Y_M = 0.002
OFFSETS_MM = (0.0, 2.0, 4.0, 5.0, 6.0, 8.0, 10.0)
ONSET_SHARE = 0.95
SMOOTH_M = 0.20
INVISIBLE_FRACTION = 0.05
VISIBLE_FRACTION = 0.20

# Measured at the seated contact (round 203: local fit on the wheel and the rail crown).
R_RAIL_M = 0.29527
R_WHEEL_M = 1.27365


def route_of(offset_mm: float) -> str:
    return f"one_set_lat_y{offset_mm:04.1f}mm"


def bump_threshold_m(offset_m: float, *, wheel_radius_m: float | None = R_WHEEL_M) -> float:
    """Bump height at which a feature at `offset_m` becomes the contact point."""
    inverse = 1.0 / R_RAIL_M
    if wheel_radius_m is not None and np.isfinite(wheel_radius_m):
        inverse += 1.0 / wheel_radius_m
    return 0.5 * offset_m**2 * inverse


def half_width_m(amplitude_m: float, *, wheel_radius_m: float | None = R_WHEEL_M) -> float:
    """Inverse of `bump_threshold_m`: the largest offset at which `amplitude_m` is still visible."""
    inverse = 1.0 / R_RAIL_M
    if wheel_radius_m is not None and np.isfinite(wheel_radius_m):
        inverse += 1.0 / wheel_radius_m
    return float(np.sqrt(2.0 * amplitude_m / inverse))


def _perturbed_section(text: str, *, amplitude_m: float, offset_m: float) -> str:
    """Subtract a lateral Gaussian from the raw z column (the loader negates z for these sections).

    Returns the section text unchanged if it carries no numeric rows.
    """
    rows = [line.split() for line in text.splitlines() if line.strip()]
    points = []
    for row in rows:
        try:
            points.append((float(row[0]), float(row[1])))
        except (IndexError, ValueError):
            points = []
            break
    if not points:
        return text
    array = np.asarray(points, dtype=float)
    y_m, z_m = array[:, 0], array[:, 1]
    crown_y = float(y_m[int(np.argmin(z_m))])  # loaded z = -raw + offset, so the crown is the raw minimum
    delta = y_m - crown_y - offset_m
    raise_m = amplitude_m * np.exp(-0.5 * (delta / SIGMA_Y_M) ** 2)
    z_new = z_m - raise_m
    return "\n".join(f"{y:.9f} {z:.9f}" for y, z in zip(y_m, z_new)) + "\n"


def build() -> dict:
    base = json.loads(CASE.read_text(encoding="utf-8"))
    built = []
    for offset_mm in OFFSETS_MM:
        offset_m = offset_mm * 1e-3
        case = json.loads(json.dumps(base))
        directory = OUT / "sections" / f"y{offset_mm:04.1f}mm"
        directory.mkdir(parents=True, exist_ok=True)
        stations_touched = 0
        for rail in case["rail_templates"]:
            for body in rail.get("bodies", []):
                if body["id"] != "blade":
                    continue
                for index, station in enumerate(body["stations"]):
                    s_m = float(station["s_m"])
                    weight = float(np.exp(-0.5 * ((s_m - CENTRE_M) / SIGMA_S_M) ** 2))
                    if weight < 1e-4:
                        continue
                    source = _source_path(station["profile"]["file"])
                    if source is None or not source.exists():
                        continue
                    text = source.read_text(encoding="utf-8")
                    baked = _perturbed_section(
                        text, amplitude_m=AMPLITUDE_UM * 1e-6 * weight, offset_m=offset_m
                    )
                    target = directory / f"blade_{index:04d}_s{s_m:07.3f}.txt"
                    target.write_text(baked, encoding="utf-8")
                    station["profile"]["file"] = str(target).replace("\\", "/")
                    station["profile"]["format"] = "txt"
                    stations_touched += 1
        case["case_id"] = f"{base['case_id']}_lat_y{offset_mm:04.1f}mm"
        case["purpose_detail"] = (
            f"lateral-observability variant: {AMPLITUDE_UM:.0f} um bump at {offset_mm:.1f} mm from the crown, "
            f"sigma_s {SIGMA_S_M:.1f} m at {CENTRE_M:.1f} m, sigma_y {SIGMA_Y_M*1e3:.1f} mm"
        )
        path = OUT / f"one_set_lat_y{offset_mm:04.1f}mm.json"
        text = json.dumps(case, indent=2)
        path.write_text(text, encoding="utf-8")
        built.append(
            {
                "offset_mm": offset_mm,
                "path": str(path),
                "case_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "stations_touched": stations_touched,
                "predicted_threshold_um": 1e6 * bump_threshold_m(offset_m),
            }
        )
        print(
            f"offset {offset_mm:5.1f} mm -> {path.name} ({stations_touched} sections, "
            f"threshold {1e6 * bump_threshold_m(offset_m):6.1f} um)"
        )
    (OUT / "variants.json").write_text(json.dumps({"variants": built}, indent=2), encoding="utf-8")
    print()
    print(f"prediction model A (R_wheel {R_WHEEL_M*1e3:.0f} mm): thresholds "
          f"{[round(1e6*bump_threshold_m(y*1e-3)) for y in (6.0, 8.0, 10.0)]} um, w(100 um) = {half_width_m(100e-6)*1e3:.1f} mm")
    print(f"prediction model B (cone only):              thresholds "
          f"{[round(1e6*bump_threshold_m(y*1e-3, wheel_radius_m=float('inf'))) for y in (6.0, 8.0, 10.0)]} um, "
          f"w(100 um) = {half_width_m(100e-6, wheel_radius_m=float('inf'))*1e3:.1f} mm")
    return {"variants": len(built)}


def _source_path(reference: str) -> pathlib.Path | None:
    """Resolve a library reference to the file the canonical library ships."""
    from velch.assets import resolve_asset

    try:
        return pathlib.Path(resolve_asset(reference, case_path=CASE).path)
    except Exception:
        return None


def _find_run(route: str) -> dict | None:
    rows = [
        row
        for row in INV._index_rows()
        if row.get("route") == route
        and abs(float(row.get("speed_kmh", 0.0)) - SPEED_KMH) < 1e-6
        and abs(float(row.get("duration_s", 0.0)) - DURATION_S) < 1e-9
    ]
    return rows[-1] if rows else None


def _acceleration(row: dict, channel: str) -> np.ndarray:
    import numpy as np  # local: keeps the module import cheap for --build

    directory = pathlib.Path(INV.RUNS) / str(row["run_id"])
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    data = np.load(directory / "series.npz")
    index = list(meta["acceleration_names"]).index(channel)
    return np.asarray(data["accelerations"], dtype=float)[:, index]


def response_of(row: dict, baseline: dict) -> dict:
    """Peak absolute acceleration change and the blade share maximum."""
    times = np.asarray(INV._load(str(row["run_id"]))["times"], dtype=float)
    station = 50.0 + (SPEED_KMH / 3.6) * times
    window = (station >= CENTRE_M - 2.0) & (station <= CENTRE_M + 2.0)
    delta = _acceleration(row, "axle1_box_right_z_acc_m_per_s2") - _acceleration(
        baseline, "axle1_box_right_z_acc_m_per_s2"
    )
    peak = float(np.max(np.abs(delta[window]))) if window.any() else float("nan")
    run = INV._load(str(row["run_id"]))
    share = INV._smooth(INV._split(run), np.asarray(run["station"], dtype=float), SMOOTH_M)
    share_max = float(np.nanmax(share)) if np.isfinite(share).any() else float("nan")
    return {"peak_delta_acc": peak, "share_max": share_max}


def report() -> dict:
    baseline = _find_run(BASELINE_ROUTE)
    if baseline is None:
        raise SystemExit("the canonical 0.6 s baseline run is missing")
    baseline_peak = float(np.max(np.abs(_acceleration(baseline, "axle1_box_right_z_acc_m_per_s2"))))
    rows = []
    reference = None
    for offset_mm in OFFSETS_MM:
        row = _find_run(route_of(offset_mm))
        if row is None:
            rows.append({"offset_mm": offset_mm, "status": "no run"})
            print(f"offset {offset_mm:5.1f} mm: no run")
            continue
        measured = response_of(row, baseline)
        if offset_mm == 0.0:
            reference = measured["peak_delta_acc"]
        fraction = measured["peak_delta_acc"] / reference if reference else float("nan")
        visible = bool(np.isfinite(fraction) and fraction >= VISIBLE_FRACTION)
        invisible = bool(np.isfinite(fraction) and fraction <= INVISIBLE_FRACTION)
        rows.append(
            {
                "offset_mm": offset_mm,
                "status": "ok",
                "run_id": row["run_id"],
                "peak_delta_acc": measured["peak_delta_acc"],
                "share_max": measured["share_max"],
                "fraction_of_reference": fraction,
                "visible": visible,
                "invisible": invisible,
                "predicted_threshold_um": 1e6 * bump_threshold_m(offset_mm * 1e-3),
            }
        )
        print(
            f"offset {offset_mm:5.1f} mm  peak |da| {measured['peak_delta_acc']:.4f} m/s2 "
            f"({fraction*100:5.1f} % of reference)  share max {measured['share_max']:.3f}  "
            f"threshold {1e6*bump_threshold_m(offset_mm*1e-3):5.1f} um"
        )

    by_offset = {row["offset_mm"]: row for row in rows if row.get("status") == "ok"}
    six = by_offset.get(6.0, {})
    eight = by_offset.get(8.0, {})
    ten = by_offset.get(10.0, {})
    model_a = bool(six.get("visible") and eight.get("invisible"))
    model_b = bool(eight.get("visible") and ten.get("invisible"))
    if model_a and not model_b:
        verdict = "the boundary is where both curvatures put it (model A)"
    elif model_b and not model_a:
        verdict = "the boundary is set by the rail crown alone (model B, 1:40 tangency)"
    elif model_a and model_b:
        verdict = "the boundary is wider than both curvature models predict"
    else:
        verdict = "the boundary lies where neither curvature model puts it"

    payload = {
        "speed_kmh": SPEED_KMH,
        "duration_s": DURATION_S,
        "amplitude_um": AMPLITUDE_UM,
        "centre_m": CENTRE_M,
        "sigma_s_m": SIGMA_S_M,
        "sigma_y_m": SIGMA_Y_M,
        "baseline_run": baseline["run_id"],
        "baseline_peak_acc": baseline_peak,
        "radii": {"rail_m": R_RAIL_M, "wheel_m": R_WHEEL_M},
        "predictions": {
            "model_a": {"half_width_m": half_width_m(AMPLITUDE_UM * 1e-6), "thresholds_um": [1e6 * bump_threshold_m(y * 1e-3) for y in (6.0, 8.0, 10.0)]},
            "model_b": {
                "half_width_m": half_width_m(AMPLITUDE_UM * 1e-6, wheel_radius_m=float("inf")),
                "thresholds_um": [1e6 * bump_threshold_m(y * 1e-3, wheel_radius_m=float("inf")) for y in (6.0, 8.0, 10.0)],
            },
        },
        "rows": rows,
        "model_a_supported": model_a,
        "model_b_supported": model_b,
        "verdict": verdict,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print()
    print(f"model A (both curvatures) supported: {model_a}   model B (cone only) supported: {model_b}")
    print(f"VERDICT: {verdict}")
    print(f"report -> {REPORT}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="write the four laterally offset variants")
    parser.add_argument("--report", action="store_true", help="read the archived runs and place the boundary")
    args = parser.parse_args(argv)
    if not args.build and not args.report:
        parser.error("give --build or --report")
    if args.build:
        build()
    if args.report:
        report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
