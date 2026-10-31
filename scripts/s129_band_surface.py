"""M7 step 6: join two passes into one band surface, and check it is single-valued.

Round 271 showed one fit recovers a 60 um bump on two passes whose contacts sit 4.6 mm apart.  A
*field* needs one more property that two separate successes do not give: the two columns must agree
where they meet, otherwise "z(s, y)" is two profiles wearing one name.

This script does the join, and reports three things the taskbook asks for:

  * each column against the truth it was built from (the same 60 um gaussian);
  * the two columns against **each other** -- the disagreement is the quantity that decides whether a
    merged surface is single-valued at all;
  * the observed region: what fraction of the 37.15 mm riding surface the two bands actually cover.

One framing note that has to stay visible.  In this test the run's own geometry is the PRR-derived
surface (the drawn blade sections, round 233), so "compare with the PRR surface" reduces to comparing
with the bump we added on top of it.  A literal recovered-versus-PRR comparison needs a measured
profile the project does not have (C level, round 3 of the taskbook); what can be verified here is
that the estimator reproduces the only difference from PRR that exists, at two lateral positions, and
that the two positions agree.

No simulation is run: both fits are read from round 271's report.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s113_profile_inversion as base  # noqa: E402
import s123_m7_assembly as assembly  # noqa: E402
import s124_joint_inversion as joint  # noqa: E402

SOURCE = ROOT / "reports" / "load_split_inversion_2026-10-31" / "band_assembly.json"
COVERAGE = ROOT / "reports" / "load_split_inversion_2026-10-31" / "lateral_coverage.json"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "band_surface.json"

# contact position of each pass relative to the crown, from round 270's seated sweep
CONTACT_MM = {"moved pass": -3.3, "control at nominal gauge": -7.9}
HALF_BAND_MM = 8.0            # half width of one pass's contact band (round 249/270: 16 mm)
HEAD_MM = 37.15               # 1 mm-deep riding surface, round 249
ABSOLUTE_LIMIT_UM = assembly.ABSOLUTE_LIMIT_UM
BIN_M = assembly.BIN_M
Y_REF_UM = assembly.Y_REF_UM
WINDOW_FRACTION = assembly.WINDOW_FRACTION


def column(row: dict) -> tuple[np.ndarray, np.ndarray]:
    """The fitted profile of one pass on the common station grid."""
    run = base._load(row["fit"]["run_id"])
    stations = np.asarray(run["station"], dtype=float)
    amplitude = float(row["fit"]["amplitude_um"])
    centre = float(row["fit"]["centre_m"])
    z = amplitude * np.exp(-0.5 * ((stations - centre) / joint.WIDTH_M) ** 2)
    return stations, z


def truth_on(stations: np.ndarray, amplitude_um: float) -> np.ndarray:
    return base._true_bump(stations, amplitude_um)


def p95_window(error: np.ndarray, reference: np.ndarray) -> float:
    peak = float(np.max(np.abs(reference)))
    if peak <= 0.0:
        return float("nan")
    window = np.abs(reference) >= WINDOW_FRACTION * peak
    return float(np.percentile(np.abs(error[window]), 95.0))


def worst_bin(error: np.ndarray, reference: np.ndarray, stations: np.ndarray) -> float:
    peak = float(np.max(np.abs(reference)))
    window = np.abs(reference) >= WINDOW_FRACTION * peak
    worst = 0.0
    start = float(stations[window].min())
    stop = float(stations[window].max())
    for edge in np.arange(start, stop, BIN_M):
        inside = window & (stations >= edge) & (stations < edge + BIN_M)
        if not inside.any():
            continue
        denominator = max(float(np.max(np.abs(reference[inside]))), Y_REF_UM)
        worst = max(worst, 100.0 * float(np.max(np.abs(error[inside]))) / denominator)
    return worst


def observed_region() -> dict:
    bands = []
    for label, contact in CONTACT_MM.items():
        bands.append({"label": label, "y_centre_mm": contact,
                      "y_lo_mm": contact - HALF_BAND_MM, "y_hi_mm": contact + HALF_BAND_MM})
    xs = np.arange(-HEAD_MM / 2.0, HEAD_MM / 2.0, 0.1)
    hit = np.zeros_like(xs, dtype=bool)
    for band in bands:
        hit |= (xs >= band["y_lo_mm"]) & (xs <= band["y_hi_mm"])
    return {"head_mm": HEAD_MM, "bands": bands,
            "coverage": float(hit.mean()),
            "covered_mm": float(hit.sum() * 0.1),
            "span_mm": [float(min(band["y_lo_mm"] for band in bands)),
                        float(max(band["y_hi_mm"] for band in bands))]}


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"{SOURCE.name} missing; run scripts/s128_band_assembly.py --report first")
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))

    columns = []
    for row in payload["rows"]:
        stations, z = column(row)
        truth = truth_on(stations, float(row["truth_um"]))
        columns.append({"label": row["label"], "delta_mm": row["delta_mm"],
                        "y_contact_mm": CONTACT_MM[row["label"]],
                        "amplitude_um": float(row["fit"]["amplitude_um"]),
                        "centre_m": float(row["fit"]["centre_m"]),
                        "stations": stations, "z": z, "truth": truth})

    print(f"{'column':26s} {'y_c mm':>8} {'truth':>7} {'peak':>7} {'p95 um':>8} {'worst %':>8}  G-ABS")
    for entry in columns:
        error = entry["z"] - entry["truth"]
        entry["p95_um"] = p95_window(error, entry["truth"])
        entry["worst_bin_relative_pct"] = worst_bin(error, entry["truth"], entry["stations"])
        entry["gates"] = {"G-ABS": entry["p95_um"] <= ABSOLUTE_LIMIT_UM}
        print(f"{entry['label']:26s} {entry['y_contact_mm']:+8.1f} {float(np.max(np.abs(entry['truth']))):7.1f} "
              f"{float(np.max(np.abs(entry['z']))):7.1f} {entry['p95_um']:8.2f} "
              f"{entry['worst_bin_relative_pct']:8.2f}  {'PASS' if entry['gates']['G-ABS'] else 'FAIL'}")

    # the new question: do the two columns agree where a merged surface would need them to?
    first, second = columns[0], columns[1]
    shared = np.intersect1d(first["stations"], second["stations"])
    if shared.size == 0:
        raise SystemExit("the two passes share no station; they cannot be joined")
    index_a = np.searchsorted(first["stations"], shared)
    index_b = np.searchsorted(second["stations"], shared)
    difference = first["z"][index_a] - second["z"][index_b]
    reference = 0.5 * (np.abs(first["truth"][index_a]) + np.abs(second["truth"][index_b]))
    consistency_p95 = p95_window(difference, reference)
    print(f"\ncolumns disagree by p95 {consistency_p95:.2f} um over {shared.size} shared stations "
          f"(max {float(np.max(np.abs(difference))):.2f} um)")

    region = observed_region()
    print(f"observed region: {region['covered_mm']:.1f} mm of {region['head_mm']:.2f} mm "
          f"= {100.0 * region['coverage']:.1f} %  (two 16 mm bands, span "
          f"{region['span_mm'][0]:+.1f} .. {region['span_mm'][1]:+.1f} mm)")

    gates = {"G-ABS per column": all(entry["gates"]["G-ABS"] for entry in columns),
             "G-CONSISTENCY": consistency_p95 <= ABSOLUTE_LIMIT_UM,
             "G-COV (report only)": True}
    verdict = ("the two passes join into one single-valued band surface"
               if gates["G-ABS per column"] and gates["G-CONSISTENCY"]
               else "the columns disagree by more than the absolute gate; the join is not single-valued")
    print("\n" + "/".join(f"{name}: {'PASS' if ok else 'FAIL'}" for name, ok in gates.items()))
    print(f"VERDICT: {verdict}")

    report = {"source_report": SOURCE.name, "width_m_prior": joint.WIDTH_M,
              "columns": [{key: value for key, value in entry.items()
                           if key not in ("stations", "z", "truth")} for entry in columns],
              "consistency": {"shared_stations": int(shared.size),
                              "p95_um": consistency_p95,
                              "max_um": float(np.max(np.abs(difference)))},
              "observed_region": region, "gates": gates, "verdict": verdict}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
