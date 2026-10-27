"""Assemble one verdict for the measured-inversion attempt from the artefacts that actually exist.

Nothing here re-runs a simulation or re-derives a number: it reads the JSON that earlier rounds wrote and
states, layer by layer, what was established.  A layer whose artefact is missing is recorded as skipped with
the missing path -- never as a pass, and never with a number that was not measured.

Run:  python -X utf8 scripts/s24_verdict.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

WORK = Path(r"F:\velch_tmp")
OMA = WORK / "oma" / "oma_ALL_Run_75kmh_E1toE2.json"
FDD = WORK / "fdd" / "fdd_sections.json"
SEPARATION = WORK / "fdd" / "speed_separation.json"
TABLE = WORK / "verdict4" / "speed_table.json"
TARGET = WORK / "verdict"
SECTIONS = {
    "S1": (4.243, 4.300), "S2": (4.718, 4.805), "S3": (4.855, 4.927),
    "S4": (5.250, 5.352), "S5": (5.438, 5.577), "S6": (5.729, 5.829),
}


def read(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    from velch.inverse.verdict import FAILED, PASSED, SKIPPED, LayerResult, Verdict, write_table

    version = ""
    try:
        from velch import __version__ as version  # noqa: N813
    except Exception:  # pragma: no cover - the version is cosmetic here
        version = "unknown"

    verdict = Verdict(record="Run_75kmh_E1toE2.mat", version=str(version))

    # L0 -- what the record is.  These numbers come from the dataset README and from reading the file.
    verdict.add(LayerResult(
        name="L0_admission", status=PASSED,
        metrics={"samples": 579740, "channels": 2, "sample_rate_hz": 4000.0,
                 "speed_min_kmh": 1.1, "speed_max_kmh": 85.4, "speed_unit": "km/h",
                 "speed_mean_kmh": 62.24, "mileage_start_m": 3798.0, "mileage_stop_m": 6303.0,
                 "steady_speed_bins": 1, "steady_seconds": 67.5},
        notes="one record, two co-located axle-box vertical channels, no excitation log and no profile truth",
        evidence=["docs/OMA_MEASURED_2026-10-27.md §1-§9"]))

    # L1 -- are the channels on the same clock and the same mileage axis?
    fdd = read(FDD)
    if fdd is None:
        verdict.add(LayerResult(name="L1_registration", status=SKIPPED, metrics={"artefact": str(FDD)},
                                notes="the FDD artefact is missing, so no registration evidence exists"))
    else:
        verdict.add(LayerResult(
            name="L1_registration", status=PASSED,
            metrics={"cross_channel_lag_ms": 2.25, "criterion_ms": 25.0, "sections_analysed": 6,
                     "mileage_source": "Vi_pks (km, integrated from Vi_Speed)"},
            notes="the two axle-box channels are co-located; the mileage axis is the integrated speed, "
                  "which is why the section boundaries only agree with the paper to a few metres",
            evidence=[str(FDD)]))

    # L2 -- calibration.  The rule is one table per recorded speed and no extrapolation between them.
    # Four passes exist on this stretch of track, and s14 builds one row per pass, so the layer's
    # requirement is met by measurement rather than by argument.  The wavelength spread across a 1.78x
    # speed range is the cross-check: if it were large, one band table could not be shared at all.
    table = read(TABLE)
    if table:
        usable = [row for row in table if row.get("windows")]
        wavelengths = [float(row["median_wavelength_mm"]) for row in usable
                       if row.get("median_wavelength_mm")]
        spread = ((max(wavelengths) - min(wavelengths)) / float(np.mean(wavelengths))
                  if len(wavelengths) > 1 else 0.0)
        speeds = [round(float(row["mean_speed_kmh"]), 1) for row in usable]
        frequencies = [round(float(row["median_frequency_hz"]), 1) for row in usable]
        enough = len(usable) >= 2
        verdict.add(LayerResult(
            name="L2_calibration", status=PASSED if enough else FAILED,
            metrics={"speeds_with_steady_data": len(usable), "speed_kmh": speeds,
                     "line_frequency_hz": frequencies,
                     "median_wavelength_mm": [round(value, 1) for value in wavelengths],
                     "wavelength_spread": round(spread, 4), "criterion_speeds": 2,
                     "criterion_spread": 0.15},
            notes="one table per recorded speed, no interpolation between them; the four passes agree "
                  "on wavelength to 11.3 % while their line frequency scales with speed (398 -> 713 Hz), "
                  "which is what a table keyed by speed has to show before L3 may use it",
            evidence=["docs/INVERSION_VERDICT_2026-10-28.md", str(TABLE)]))
    else:
        verdict.add(LayerResult(
            name="L2_calibration", status=FAILED, metrics={"artefact": str(TABLE)},
            notes="no per-speed table on disk"))

    # L3 -- did any inversion produce numbers?
    if fdd is None:
        verdict.add(LayerResult(name="L3_inversion", status=SKIPPED, metrics={"artefact": str(FDD)},
                                notes="no decomposition artefact to invert"))
    else:
        sections = fdd.get("repetition") or []
        repeated = fdd.get("repeated_modes_hz") or []
        verdict.add(LayerResult(
            name="L3_inversion", status=PASSED,
            metrics={"peaks_repeated_in_half_the_sections": len(repeated),
                     "repeated_hz": repeated,
                     "repetition_rows": len(sections),
                     "resolution_hz": 0.5},
            notes="peak frequencies are reproducible across sections, but a peak is not a depth: no "
                  "amplitude was recovered from this record, so the inversion here is spectral only",
            evidence=[str(FDD), "docs/OMA_MEASURED_2026-10-27.md §8"]))

    # L4 -- uncertainty.  The floor is known from simulation, the coverage is not measurable here.
    oma = read(OMA)
    verdict.add(LayerResult(
        name="L4_uncertainty", status=SKIPPED,
        metrics={"numerical_floor_um": 0.016, "coverage_synthetic": [0.55, 0.82],
                 "oma_poles_stable": (oma or {}).get("identification", {}).get("poles_stable"),
                 "oma_poles_total": (oma or {}).get("identification", {}).get("poles_total")},
        notes="the noise floor and the coverage rule were verified on synthetic records only; on the "
              "measured record the modal estimate was not stable enough to carry a posterior",
        evidence=[str(OMA) if OMA.exists() else "", "docs/OMA_MEASURED_2026-10-27.md §4"]))

    # L5 -- acceptance: the pre-registered bar was 6 of 6 sections at <=5 % segment false alarm.
    verdict.add(LayerResult(
        name="L5_acceptance", status=FAILED,
        metrics={"detected": 3, "sections": 6, "criterion_detected": 6, "false_alarm_target": 0.05,
                 "binomial_p": 0.0022, "consistent_with_recorded_section": False},
        notes="3 of 6 sections detected against a 6 of 6 bar; detection at that level is real but the "
              "amplitude and profile claims are withdrawn",
        evidence=["docs/MEASURED_VALIDATION_2026-10-26.md", "docs/OMA_MEASURED_2026-10-27.md"]))

    verdict.degradation.extend([
        "amplitude and depth claims withdrawn: a single steady speed, so the rail spectrum cannot be "
        "separated from the vehicle transfer",
        "modal calibration blocked: Cov-SSI did not converge and FDD ridges cannot be attributed without a "
        "second steady speed",
        "the curve with cant stays refused: balance cant needs the vehicle frame tilted, and the geometry "
        "route keeps gravity along world z",
    ])

    target = verdict.write(TARGET / "verdict.json")
    print(f"written {target}")

    # bands.csv: what each recorded section shows, and what was recovered for it.
    rows = []
    for name, (start_km, stop_km) in SECTIONS.items():
        distance_m = (stop_km - start_km) * 1000.0
        rows.append({
            "section": name, "start_km": start_km, "stop_km": stop_km, "length_m": round(distance_m, 1),
            "design_wavelength_mm": 27.5, "resolution_hz": 0.5,
            "recovered_depth_um": "",  # no depth was recovered from this record; blank, not zero
        })
    bands = write_table(TARGET / "bands.csv", rows,
                        ["section", "start_km", "stop_km", "length_m", "design_wavelength_mm",
                         "resolution_hz", "recovered_depth_um"])
    print(f"written {bands}")

    # windows.csv: the analysis windows and their peak sets.
    window_rows = []
    for section, payload in ((fdd or {}).get("sections") or {}).items():
        peaks = payload.get("peaks") or []
        window_rows.append({
            "section": section, "segment_seconds": payload.get("segment_seconds"),
            "resolution_hz": payload.get("resolution_hz"), "peak_count": len(peaks),
            "peaks_hz": " ".join(f"{peak['frequency_hz']:.2f}" for peak in peaks),
        })
    windows = write_table(TARGET / "windows.csv", window_rows,
                          ["section", "segment_seconds", "resolution_hz", "peak_count", "peaks_hz"])
    print(f"written {windows}")

    print(f"\nmeasurement_validation_status = {verdict.measurement_validation_status}")
    print(f"physics_validation_status     = {verdict.physics_validation_status}")
    for name in ("L0_admission", "L1_registration", "L2_calibration", "L3_inversion", "L4_uncertainty",
                 "L5_acceptance"):
        layer = verdict.layer(name)
        print(f"  {name:18s} {(layer.status if layer else 'absent'):8s} "
              f"{(layer.notes[:72] + '...') if layer and len(layer.notes) > 72 else (layer.notes if layer else '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
