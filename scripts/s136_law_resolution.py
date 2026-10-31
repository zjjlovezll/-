"""M8 step 7: is the composition floor an interpolation artefact of a 7-knot lookup?

Round 278 ruled out the u-range clamp (0.0 % clamped) and left the mechanism open.  There is one more
cheap explanation before the contact layer gets rebuilt: the measured law is a **knot lookup**.  The
station sweep in round 255 recorded sigma at seven offsets (250, 100, 50, 0, -50, -100, -200 um), and
`s124.share_law` interpolates them linearly.  A profile whose stations land *between* knots is then
predicted by a straight line across a steep, curved segment -- and the more components a profile has,
the more of its stations sit in that steep segment rather than on a knot.

That hypothesis makes two falsifiable predictions, and this script measures both with no new simulation:

    P1  the six-component profile has a larger share of its stations in the steep band (the two knots
        that bracket sigma = 0.2 .. 0.8) than the two-peak profile;
    P2  within a run, |error| grows with the distance to the nearest knot.

Pre-registered reading: if both hold, the floor is dominated by interpolation resolution and the fix is
to measure the law densely in the steep band -- not to rebuild the contact layer.
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
import s130_two_peak as two_peak  # noqa: E402
import s135_floor_diagnosis as diagnosis  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "law_resolution.json"
FIT_LO_M, FIT_HI_M = 57.5, 63.5
STEEP_LO, STEEP_HI = 0.2, 0.8


def _knots() -> tuple[np.ndarray, np.ndarray]:
    build_law_result = assembly.build_law()
    curves, _ = law._measured_curves()
    curve_u, curve_sigma = curves[float(build_law_result[2]["station_m"])]
    order = np.argsort(curve_u)
    return np.asarray(curve_u)[order], np.asarray(curve_sigma)[order]


def _state(route: str) -> dict:
    build_law_result = assembly.build_law()
    sigma_of = joint.share_law(build_law_result)
    null_state = two_peak._null_state()
    run = base._load(base._run_id(route))
    stations = np.asarray(run["station"], dtype=float)
    observed = base._smooth(base._split(run), stations, base.SMOOTH_M)
    widths = law._width_at(stations, *law._width_table())
    u0 = np.interp(stations, null_state["stations"], null_state["u0"], left=np.nan, right=np.nan)
    usable = (np.isfinite(observed) & np.isfinite(u0) & (stations >= FIT_LO_M) & (stations <= FIT_HI_M)
              & (observed > joint.SHARE_LO) & (observed < joint.SHARE_HI))
    return {"stations": stations, "observed": observed, "widths": widths, "u0": u0,
            "usable": usable, "sigma_of": sigma_of}


def analyse(route: str, truth_of) -> dict:
    state = _state(route)
    knots_u, knots_sigma = _knots()
    usable = state["usable"]
    stations = state["stations"][usable]
    u = state["u0"][usable] + np.asarray(truth_of(stations), dtype=float)
    observed = state["observed"][usable]
    predicted = state["sigma_of"](u, state["widths"][usable])
    error = np.abs(predicted - observed)

    steep = (knots_sigma >= STEEP_LO) & (knots_sigma <= STEEP_HI)
    if steep.sum() >= 2:
        steep_lo, steep_hi = float(knots_u[steep].min()), float(knots_u[steep].max())
    else:                                     # fall back to the full span
        steep_lo, steep_hi = float(knots_u.min()), float(knots_u.max())
    in_steep = (u >= steep_lo) & (u <= steep_hi)

    nearest = np.min(np.abs(u[:, None] - knots_u[None, :]), axis=1)
    gap_between = nearest[u > knots_u[0]]
    correlation = float("nan")
    if gap_between.size >= 8 and np.isfinite(error).all():
        correlation = float(np.corrcoef(gap_between, error[u > knots_u[0]])[0, 1])
    return {
        "route": route, "usable": int(usable.sum()),
        "steep_band_u": [steep_lo, steep_hi],
        "steep_fraction": float(np.mean(in_steep)),
        "nearest_knot_median_um": float(np.median(nearest)),
        "nearest_knot_p90_um": float(np.percentile(nearest, 90)),
        "floor_um_share": float(np.sqrt(np.mean((predicted - observed) ** 2))),
        "mean_abs_error": float(np.mean(error)),
        "corr_error_vs_knot_distance": correlation,
    }


def main() -> int:
    rows = [analyse(route, truth) for route, truth in diagnosis.RUNS.values()]
    rows.append(analyse("one_set_random", diagnosis._random_profile))
    six = rows[-1]
    two = rows[0]
    p1 = six["steep_fraction"] > two["steep_fraction"]
    p2 = bool(np.isfinite(six["corr_error_vs_knot_distance"])
              and six["corr_error_vs_knot_distance"] >= 0.5)
    if p1 and p2:
        verdict = ("the floor is dominated by interpolation resolution: the six-component profile puts "
                   "more stations between knots and the error grows with the distance to a knot, so the "
                   "fix is to measure the law densely in the steep band")
    elif p1 and not p2:
        verdict = ("the profile does sit between knots more often, but the error does not follow the knot "
                   "distance, so resolution alone does not explain the floor")
    elif p2 and not p1:
        verdict = ("the error follows the knot distance, but the six-component profile is not pressed into "
                   "the steep band more than the two-peak one")
    else:
        verdict = ("neither prediction holds: interpolation resolution does not explain the floor, so the "
                   "per-station assumption itself has to be re-measured")
    payload = {"knots_u": [float(value) for value in _knots()[0]],
               "knots_sigma": [float(value) for value in _knots()[1]],
               "runs": rows, "p1_steep_fraction": bool(p1), "p2_error_vs_knot_distance": p2,
               "verdict": verdict}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"knots u: {[round(float(v), 1) for v in payload['knots_u']]}")
    print(f"{'run':28s} {'usable':>7s} {'steep%':>7s} {'knot med':>9s} {'knot p90':>9s}"
          f" {'floor':>7s} {'corr':>7s}")
    for row in rows:
        print(f"{row['route']:28s} {row['usable']:7d} {100*row['steep_fraction']:6.1f}%"
              f" {row['nearest_knot_median_um']:9.1f} {row['nearest_knot_p90_um']:9.1f}"
              f" {row['floor_um_share']:7.4f} {row['corr_error_vs_knot_distance']:7.3f}")
    print(f"P1 steep fraction grows with components: {'YES' if p1 else 'NO'}")
    print(f"P2 error follows the knot distance: {'YES' if p2 else 'NO'}")
    print(f"VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
