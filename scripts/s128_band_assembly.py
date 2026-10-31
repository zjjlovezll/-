"""M7 step 4: does the inversion still work when the pass sits somewhere else on the head?

Rounds 261-262 fitted one amplitude and one centre from a single pass at nominal gauge, where the
contact sits 7.9 mm inboard of the crown.  Round 270 moved the contact across the head with the gauge
(1.28 mm of slide per millimetre) and measured that the band can be pushed as far as 0.7 mm inboard of
the crown (delta = +8 mm).  If the inversion only works at the setting it was calibrated on, then
"assemble the band from several passes" is not available and the light band stays one 16 mm strip.

This step asks the cheapest decisive version of that question: take one pass at delta = +4 mm (contact
3.3 mm inboard of the crown, 4.6 mm away from where every calibration run sits) carrying a known
60 um bump, and run exactly the round-261 fit on it, with the null-calibrated operating point taken
from the delta = +4 mm run itself.

Gates are the round-261 ones, unchanged:
    G-ABS  p95(|z_hat - z|) <= 22 um where the truth exceeds 10 % of its peak
    G-REL  worst 2 mm bin |e| / max(|z|, 500 um) <= 2 %
    G-LOC  |peak station - truth peak| <= 0.20 m

The control is the same amplitude at nominal gauge (already archived), so the two numbers are read
with one ruler.
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
import s123_m7_assembly as assembly  # noqa: E402
import s124_joint_inversion as joint  # noqa: E402

CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s128"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "band_assembly.json"

DELTA_MM = 4.0
AMPLITUDE_UM = 60.0
CENTRE_M = base.CENTRE_M
SIGMA_S_M = base.SIGMA_M
SPEED_KMH = base.SPEED_KMH
DURATION_S = base.DURATION_S
SHARE_LO, SHARE_HI = joint.SHARE_LO, joint.SHARE_HI


def route_of(delta_mm: float, amplitude_um: float | None) -> str:
    """Archive label of the run this variant produces (s99 labels a run by its case file stem)."""
    gauge = f"one_set_gauge{delta_mm:+.0f}mm"
    return gauge if amplitude_um is None else f"{gauge}_bump{amplitude_um:05.1f}um"


def existing_routes(delta_mm: float, amplitude_um: float) -> tuple[str, str]:
    """The two runs the fit needs, using the archive's own names for the nominal gauge sessions.

    The nominal-gauge null is the canonical session (`straight_one_set`) and its bumps are the round-257
    campaign (`one_set_bump060.0um`); only the moved-gauge sessions carry a gauge in their label.  This
    keeps the control comparable to round 261 instead of requiring a duplicate rerun.
    """
    if delta_mm == 0.0:
        return assembly.BASELINE_ROUTE, f"one_set_bump{amplitude_um:05.1f}um"
    gauge = route_of(delta_mm, None)
    return gauge, f"{gauge}_bump{amplitude_um:05.1f}um"


def _right_rail(case: dict) -> dict:
    return case["rail_templates"][1]  # the same convention s126 uses: index 1 is the right rail


def build() -> int:
    """Gauge shift on the right rail, then the bump on the blade body's stations."""
    OUT.mkdir(parents=True, exist_ok=True)
    case = json.loads(CASE.read_text(encoding="utf-8"))
    rail = _right_rail(case)

    # gauge: shift every station of the right rail, template stations and body stations alike
    for station in rail["stations"]:
        profile = station["profile"]
        profile["y_offset_m"] = float(profile.get("y_offset_m", 0.0)) + DELTA_MM / 1000.0
    for body in rail.get("bodies") or []:
        for station in body["stations"]:
            profile = station["profile"]
            profile["y_offset_m"] = float(profile.get("y_offset_m", 0.0)) + DELTA_MM / 1000.0

    # bump: only the blade body carries it
    touched = 0
    for body in rail.get("bodies") or []:
        if body.get("id") != "blade":
            continue
        for station in body["stations"]:
            s_m = float(station["s_m"])
            weight = np.exp(-0.5 * ((s_m - CENTRE_M) / SIGMA_S_M) ** 2)
            station["profile"]["z_offset_m"] = float(station["profile"].get("z_offset_m", 0.0)) + (
                AMPLITUDE_UM * 1e-6 * float(weight))
            touched += 1

    case["case_id"] = f"{case['case_id']}_{route_of(DELTA_MM, AMPLITUDE_UM)}"
    case["purpose_detail"] = (case.get("purpose_detail", "") +
                             f" | band-assembly variant: gauge {DELTA_MM:+.1f} mm, bump {AMPLITUDE_UM:.1f} um")
    path = OUT / f"{route_of(DELTA_MM, AMPLITUDE_UM)}.json"
    path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    print(f"{DELTA_MM:+.1f} mm gauge, {AMPLITUDE_UM:.1f} um bump -> {path.name} ({touched} blade stations)")
    return 0


def _null_state(route: str) -> dict:
    build_law_result = assembly.build_law()
    _, invert, _ = build_law_result
    half_gap_of = build_law_result[0]
    null_run = base._load(base._run_id(route))
    stations = null_run["station"]
    share = base._smooth(base._split(null_run), stations, base.SMOOTH_M)
    widths = law._width_at(stations, *law._width_table())
    u0 = np.full_like(share, np.nan)
    usable = np.isfinite(share) & (share > SHARE_LO) & (share < SHARE_HI)
    for index in np.nonzero(usable)[0]:
        u0[index] = invert(float(share[index]), half_gap_of(float(widths[index])))
    return {"stations": stations, "share_raw": share, "u0": u0, "run_id": base._run_id(route)}


def report() -> int:
    build_law_result = assembly.build_law()
    sigma_of = joint.share_law(build_law_result)

    rows = []
    for delta_mm, amplitude_um, label in ((DELTA_MM, AMPLITUDE_UM, "moved pass"),
                                          (0.0, AMPLITUDE_UM, "control at nominal gauge")):
        null_route, bump_route = existing_routes(delta_mm, amplitude_um)
        try:
            null_state = _null_state(null_route)
            fit = joint.fit_one(bump_route, sigma_of, null_state)
        except SystemExit as failure:
            print(f"{label}: {failure}")
            continue
        scored = joint.score_fit(fit, amplitude_um)
        rows.append({"label": label, "delta_mm": delta_mm, "truth_um": amplitude_um,
                     "null_route": null_route, "bump_route": bump_route,
                     "fit": {key: value for key, value in fit.items() if key != "stations"},
                     **{key: value for key, value in scored.items() if key != "stations"}})

    print(f"{'pass':28s} {'delta':>6} {'truth':>6} {'fit A':>7} {'rel %':>6} {'centre':>8} "
          f"{'p95 um':>7} {'worst %':>7} {'loc m':>6}  gates")
    for row in rows:
        gates = row["gates"]
        print(f"{row['label']:28s} {row['delta_mm']:+6.1f} {row['truth_um']:6.1f} "
              f"{row['fit']['amplitude_um']:7.1f} {row['amplitude_relative_pct']:6.2f} "
              f"{row['fit']['centre_m']:8.3f} {row['p95_um']:7.2f} "
              f"{row['worst_bin_relative_pct']:7.2f} {row['peak_error_m']:6.3f}  "
              + "/".join("PASS" if gates[key] else "FAIL" for key in ("G-ABS", "G-REL", "G-LOC")))

    moved = [row for row in rows if row["delta_mm"] != 0.0]
    verdict = ("the inversion carries across the head" if moved and all(all(r["gates"].values()) for r in moved)
               else "the inversion does not carry across the head at this setting")
    payload = {"delta_mm": DELTA_MM, "amplitude_um": AMPLITUDE_UM, "width_m_prior": joint.WIDTH_M,
               "fit_window_m": [joint.FIT_LO_M, joint.FIT_HI_M], "rows": rows, "verdict": verdict}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nVERDICT: {verdict}")
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
