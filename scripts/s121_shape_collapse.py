"""Does the onset station collapse onto one shape-independent curve?

Round 257 measured `onset` for six amplitudes at one bump shape (centre 58.5 m, sigma 1.2 m) and found it
carried the amplitude at 1.4-4.7 um per output frame.  A calibration is not an operator: if the bump is
narrower, or sits at a different station, the onset moves.  The question this probe answers is whether it
moves *predictably*.

Hypothesis H, written before any of these runs existed:

    onset - centre = sigma * F(amplitude)

i.e. the crossing sits a fixed number of sigmas into the ramp, and the number depends on the amplitude only.
Two consequences are separately testable with four runs at a single amplitude (100 um):

    (a) scaling   at centre 58.5:  onset(sigma = 0.6) - 58.5  and  onset(sigma = 2.4) - 58.5
        should be 0.5x and 2.0x of the measured 1.2 m offset (-0.244 m, i.e. -0.122 and -0.488 m),
        within +-25 % of those proportional predictions;

    (b) translation   at sigma 1.2:  onset(centre = 57.5) - 57.5  and  onset(centre = 59.5) - 59.5
        should both equal the same offset as the 58.5 run, within +-0.05 m.

If both hold, F can be tabulated from the round-257 campaign and applied to any (centre, sigma) at 80 km/h.
If (a) fails while (b) holds, the offset depends on the shape in a way a single sigma number cannot carry, and
the operator has to be classified by shape rather than scaled by sigma.  Either outcome is a result; neither
is a reason to restate a gate.

Caveats recorded up front: the scaling test has two points on one axis and the translation test only moves the
bump by 1 m either way, so "collapse" here means "consistent with proportionality", not "proven universal".

Usage:
    python -X utf8 scripts/s121_shape_collapse.py --build
    # four runs: scripts/s99_run_archive.py --case ../scratch/s121/<file> --speed-kmh 80 --duration 0.6
    python -X utf8 scripts/s121_shape_collapse.py --report

Outputs:
    scratch/s121/one_set_shape_s<sigma>_c<centre>.json     case variants
    scratch/s121/variants.json                             what was built
    reports/load_split_inversion_2026-10-31/shape_collapse.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import s113_profile_inversion as INV  # noqa: E402

CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s121"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "shape_collapse.json"

SPEED_KMH = 80.0
DURATION_S = 0.6
AMPLITUDE_UM = 100.0
ONSET_SHARE = 0.95
SMOOTH_M = 0.20
GRID_M = (SPEED_KMH / 3.6) * 5.0e-4
REFERENCE = {"sigma_m": 1.2, "centre_m": 58.5}

# (sigma, centre) at a single amplitude: two on the scaling axis, two on the translation axis.
SHAPES = (
    (0.6, 58.5),
    (2.4, 58.5),
    (1.2, 57.5),
    (1.2, 59.5),
)


def route_of(sigma: float, centre: float) -> str:
    return f"one_set_shape_s{sigma:.1f}_c{centre:.1f}"


def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    import hashlib

    base = json.loads(CASE.read_text(encoding="utf-8"))
    tables = base["templates"] if "templates" in base else base["rail_templates"]
    variants = []
    for sigma, centre in SHAPES:
        case = json.loads(json.dumps(base))
        rails = case["rail_templates"]
        touched = 0
        for rail in rails:
            for body in rail.get("bodies", []):
                if body["id"] != "blade":
                    continue
                for station in body["stations"]:
                    s_m = float(station["s_m"])
                    value = AMPLITUDE_UM * 1e-6 * np.exp(-0.5 * ((s_m - centre) / sigma) ** 2)
                    profile = station["profile"]
                    profile["z_offset_m"] = float(profile.get("z_offset_m", 0.0)) + float(value)
                    touched += 1
        case["case_id"] = f"{base['case_id']}_shape_s{sigma:.1f}_c{centre:.1f}"
        case["purpose_detail"] = (
            f"surface-sensitivity variant: Gaussian bump {AMPLITUDE_UM:.1f} um, sigma {sigma:.2f} m, "
            f"centre {centre:.2f} m, onset-collapse probe"
        )
        path = OUT / f"one_set_shape_s{sigma:.1f}_c{centre:.1f}.json"
        text = json.dumps(case, indent=2)
        path.write_text(text, encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        variants.append(
            {
                "sigma_m": sigma,
                "centre_m": centre,
                "amplitude_um": AMPLITUDE_UM,
                "path": str(path),
                "case_sha256": digest,
                "stations_touched": touched,
            }
        )
        print(f"sigma {sigma:.1f} m, centre {centre:.1f} m -> {path.name} ({touched} stations)")
    (OUT / "variants.json").write_text(json.dumps({"variants": variants}, indent=2), encoding="utf-8")
    return {"variants": len(variants)}


def _find_run(route: str) -> dict | None:
    rows = [r for r in INV._index_rows() if r.get("route") == route]
    rows = [r for r in rows if abs(float(r["speed_kmh"]) - SPEED_KMH) < 1e-6 and abs(float(r["duration_s"]) - DURATION_S) < 1e-9]
    if not rows:
        return None
    return rows[-1]


def onset_of(row: dict) -> tuple[float | None, float, float]:
    """Onset station, argmax station and peak share for one archived run."""
    run = INV._load(str(row["run_id"]))
    station = np.asarray(run["station"], dtype=float)
    share = INV._smooth(INV._split(run), station, SMOOTH_M)
    if not np.isfinite(share).any():
        return None, float("nan"), float("nan")
    peak_share = float(np.nanmax(share))
    peak_at = float(station[int(np.nanargmax(share))])
    index = _first_above(share, ONSET_SHARE)
    crossing = None if index is None else float(station[index])
    return crossing, peak_at, peak_share


def _first_above(share: np.ndarray, threshold: float) -> int | None:
    """Index of the first entry that reaches the threshold; NaN entries never do."""
    values = np.asarray(share, dtype=float)
    for index, value in enumerate(values):
        if np.isfinite(value) and value >= threshold:
            return index
    return None


def scaling_test(offsets: dict[float, float], reference_offset: float) -> dict:
    """Is the offset proportional to sigma, within 25 %?"""
    checks = {}
    for sigma, offset in sorted(offsets.items()):
        predicted = reference_offset * (sigma / REFERENCE["sigma_m"])
        ok = abs(offset - predicted) <= 0.25 * abs(predicted)
        checks[f"sigma_{sigma:.1f}"] = {
            "offset_m": offset,
            "predicted_m": predicted,
            "ok": bool(ok),
        }
    monotone = all(
        abs(offsets[b]) > abs(offsets[a])
        for a, b in zip(sorted(offsets), sorted(offsets)[1:])
    )
    return {"checks": checks, "monotone_in_sigma": bool(monotone), "ok": bool(monotone and all(c["ok"] for c in checks.values()))}


def translation_test(offsets: dict[float, float], reference_offset: float, tolerance_m: float = 0.05) -> dict:
    """Does moving the bump move the onset by the same amount?"""
    checks = {}
    for centre, offset in sorted(offsets.items()):
        ok = abs(offset - reference_offset) <= tolerance_m
        checks[f"centre_{centre:.1f}"] = {"offset_m": offset, "reference_offset_m": reference_offset, "ok": bool(ok)}
    return {"checks": checks, "ok": bool(all(c["ok"] for c in checks.values()))}


def report() -> dict:
    reference_offset = None
    reference_row = _find_run("one_set_bump100.0um")
    if reference_row is not None:
        crossing, _, _ = onset_of(reference_row)
        if crossing is not None:
            reference_offset = crossing - REFERENCE["centre_m"]
    if reference_offset is None:
        raise SystemExit("the 100 um reference run is missing or never saturates; cannot test the collapse")

    rows = []
    scaling: dict[float, float] = {}
    translation: dict[float, float] = {}
    for sigma, centre in SHAPES:
        route = route_of(sigma, centre)
        row = _find_run(route)
        if row is None:
            rows.append({"sigma_m": sigma, "centre_m": centre, "onset_m": None, "note": "no run"})
            print(f"sigma {sigma:.1f} centre {centre:.1f}: no run")
            continue
        crossing, peak_at, peak_share = onset_of(row)
        if crossing is None:
            rows.append({"sigma_m": sigma, "centre_m": centre, "onset_m": None, "peak_share": peak_share, "note": "never saturates"})
            print(f"sigma {sigma:.1f} centre {centre:.1f}: never saturates (max share {peak_share:.3f})")
            continue
        offset = crossing - centre
        rows.append(
            {
                "sigma_m": sigma,
                "centre_m": centre,
                "onset_m": crossing,
                "peak_m": peak_at,
                "peak_share": peak_share,
                "offset_m": offset,
                "run_id": row["run_id"],
            }
        )
        if abs(centre - REFERENCE["centre_m"]) < 1e-9:
            scaling[sigma] = offset
        if abs(sigma - REFERENCE["sigma_m"]) < 1e-9:
            translation[centre] = offset
        print(
            f"sigma {sigma:.1f} centre {centre:.1f}  onset {crossing:.3f} m  "
            f"offset {offset*1e3:+.1f} mm  peak {peak_at:.3f}  share {peak_share:.3f}"
        )

    scaling_result = scaling_test(scaling, reference_offset) if len(scaling) >= 2 else {"ok": None, "note": "fewer than two sigma points"}
    translation_result = translation_test(translation, reference_offset) if len(translation) >= 2 else {"ok": None, "note": "fewer than two centre points"}

    if scaling_result.get("ok") and translation_result.get("ok"):
        verdict = "collapsed: onset - centre = sigma * F(amplitude) is consistent with these runs"
    elif translation_result.get("ok") and scaling_result.get("ok") is False:
        verdict = "translation holds but sigma scaling does not: the offset is shape dependent beyond one sigma"
    elif scaling_result.get("ok") and translation_result.get("ok") is False:
        verdict = "sigma scaling holds but the bump centre shifts the onset non-trivially"
    else:
        verdict = "neither axis collapsed: the onset needs a shape classification, not a single number"

    payload = {
        "speed_kmh": SPEED_KMH,
        "duration_s": DURATION_S,
        "amplitude_um": AMPLITUDE_UM,
        "onset_share": ONSET_SHARE,
        "grid_m": GRID_M,
        "reference": {"sigma_m": REFERENCE["sigma_m"], "centre_m": REFERENCE["centre_m"], "offset_m": reference_offset},
        "rows": rows,
        "scaling": scaling_result,
        "translation": translation_result,
        "verdict": verdict,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print()
    print(f"reference offset at sigma 1.2 / centre 58.5 : {reference_offset*1e3:+.1f} mm")
    print(f"scaling   ok={scaling_result.get('ok')} monotone={scaling_result.get('monotone_in_sigma')}")
    for key, item in scaling_result.get("checks", {}).items():
        print(f"  {key}: offset {item['offset_m']*1e3:+.1f} mm vs predicted {item['predicted_m']*1e3:+.1f} mm -> {item['ok']}")
    print(f"translation ok={translation_result.get('ok')}")
    for key, item in translation_result.get("checks", {}).items():
        print(f"  {key}: offset {item['offset_m']*1e3:+.1f} mm -> {item['ok']}")
    print(f"VERDICT: {verdict}")
    print(f"report -> {REPORT}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="write the four shape variants")
    parser.add_argument("--report", action="store_true", help="read the archived runs and test the collapse")
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
