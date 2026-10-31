"""M8 step 8: is the missing coordinate the contact width?

Rounds 277-279 measured away four explanations for the random-profile floor (estimator, window
saturation, u-range clamp, interpolation resolution) and left one: the assumption that the share at a
station depends only on a scalar gap.  The measurement that suggests a second coordinate is the contact
half-width, which changes by 1.30x across the transition (5.75 -> 7.47 mm, round 254) and has been
archived per frame per rail since round 270.

So fit three models on the two-peak and three-peak runs and test them on the six-component random run:

    M1  the current law            sigma = law(u)                        (reference: the round-277 floor)
    M2  two coordinates            sigma = logistic((u - a0 - a1*db)/w), db = b - b_ref, b archived
                                   -- diagnostic only: b comes from the run being fitted, so a collapse
                                      here proves the coordinate is informative but is NOT actionable
    M3  one coordinate, re-mapped  sigma = logistic((u - a0 - a1*(c0 + c1*u))/w)
                                   -- actionable: b is predicted from u, fitted on the calibration runs

Pre-registered reading:

    M2 floor on the random run <= 0.02  -> the width is the missing coordinate (and M3 tells us whether
                                           it can be supplied without measuring b)
    M3 floor <= 0.02 and M2 not needed   -> the mapping's shape is wrong; re-measure the law's shape
    neither                              -> the per-station coupling is real, so the contact layer has to
                                           be re-derived (route (a))
No gate is relaxed: the floor target is still 0.02.
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
import s130_two_peak as two_peak  # noqa: E402
import s135_floor_diagnosis as diagnosis  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "width_coordinate.json"
RUNS_DIR = ROOT.parent / "scratch" / "runs"
FIT_LO_M, FIT_HI_M = 57.5, 63.5
FLOOR_TARGET = 0.02
CALIBRATION = ("one_set_twopeak", "one_set_threepeak_obs")
HOLDOUT = "one_set_random"


def _meta(run_id: str) -> dict:
    return json.loads((RUNS_DIR / run_id / "meta.json").read_text(encoding="utf-8"))


_OFFSETS: tuple[float, ...] | None = None


def _axle_offsets() -> tuple[float, ...]:
    """Axle offsets come from the loaded vehicle, not from the case JSON.

    The canonical case is `vehicle_ref`-based (round M1), so it carries no inline vehicle block: reading
    `case["vehicle"]` raises KeyError.  `load_vehicle_case` resolves the reference and the offsets.
    """
    global _OFFSETS
    if _OFFSETS is None:
        from velch.vehicle import load_vehicle_case
        case = load_vehicle_case(ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" /
                                 "cases" / "straight_one_set.json")
        _OFFSETS = tuple(float(value) for value in case.vehicle.axle_offsets_m)
    return _OFFSETS


def _station_of(run_id: str, times: np.ndarray) -> np.ndarray:
    meta = _meta(run_id)
    offsets = _axle_offsets()
    return float(meta["x_start_m"]) + float(meta["speed_kmh"]) / 3.6 * times + offsets[0]


def _panel(route: str, truth_of) -> dict:
    run_id = base._run_id(route)
    data = np.load(RUNS_DIR / run_id / "series.npz")
    meta = _meta(run_id)
    stations = _station_of(run_id, data["times"])
    rail_ids = list(meta["rail_ids"])
    column = rail_ids.index("axle1_right")
    half_width = np.asarray(data["contact_half_width_m"][:, column], dtype=float)

    null_state = two_peak._null_state()
    build_law_result = assembly.build_law()
    sigma_of = joint.share_law(build_law_result)
    observed = base._smooth(base._split(base._load(run_id)), base._load(run_id)["station"], base.SMOOTH_M)
    widths = law._width_at(base._load(run_id)["station"], *law._width_table())
    station_row = np.asarray(base._load(run_id)["station"], dtype=float)
    u0 = np.interp(station_row, null_state["stations"], null_state["u0"], left=np.nan, right=np.nan)

    # the archived half-width lives on the frame grid, the share on the station grid
    half_width_on_stations = np.interp(station_row, stations, half_width)
    usable = (np.isfinite(observed) & np.isfinite(u0) & (station_row >= FIT_LO_M)
              & (station_row <= FIT_HI_M) & (observed > joint.SHARE_LO) & (observed < joint.SHARE_HI))
    if int(usable.sum()) < 50:
        raise SystemExit(f"{route}: too few usable stations")
    u = u0[usable] + np.asarray(truth_of(station_row[usable]), dtype=float)
    share = observed[usable]
    predicted = sigma_of(u, widths[usable])

    # The width offset is measured against the un-bumped run at the same station: that removes the
    # station-dependent part of the width and leaves what the raise itself does to the contact.
    baseline_id = base._run_id("straight_one_set")
    baseline = np.load(RUNS_DIR / baseline_id / "series.npz")
    baseline_meta = _meta(baseline_id)
    baseline_column = list(baseline_meta["rail_ids"]).index("axle1_right")
    baseline_station = _station_of(baseline_id, baseline["times"])
    baseline_width = np.interp(station_row, baseline_station,
                               np.asarray(baseline["contact_half_width_m"][:, baseline_column], dtype=float))
    db = (half_width_on_stations - baseline_width)[usable] * 1e3          # mm

    return {"route": route, "run_id": run_id, "u": u, "b": half_width_on_stations[usable] * 1e3,
            "db": db, "share": share, "law_residual": predicted - share,
            "law_floor": float(np.sqrt(np.mean((predicted - share) ** 2))),
            "usable": int(usable.sum())}


def _logistic(u: np.ndarray, a0: float, a1: float, w: float, db: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(u - a0 - a1 * db) / w))


def _fit_two_coordinate(panels: list[dict]) -> dict:
    b_ref = float(np.mean(np.concatenate([panel["b"] for panel in panels])))

    def residual(params: np.ndarray) -> np.ndarray:
        a0, a1, w = params
        return np.concatenate([_logistic(panel["u"], a0, a1, w, panel["b"] - b_ref) - panel["share"]
                               for panel in panels])

    solved = least_squares(residual, np.asarray([100.0, 0.0, 30.0]),
                           bounds=([-600.0, -200.0, 5.0], [900.0, 200.0, 400.0]),
                           method="trf", xtol=1e-12, ftol=1e-12)
    return {"params": [float(v) for v in solved.x], "b_ref_mm": b_ref}


def _fit_one_coordinate(panels: list[dict], two: dict) -> dict:
    """b predicted from u on the calibration runs, so the model stays a function of u alone."""
    us = np.concatenate([panel["u"] for panel in panels])
    bs = np.concatenate([panel["b"] for panel in panels])
    slope, intercept = np.polyfit(us, bs, 1)
    a0, a1, w = two["params"]
    b_ref = two["b_ref_mm"]

    def residual(params: np.ndarray) -> np.ndarray:
        alpha, beta, width = params
        total = []
        for panel in panels:
            b_pred = intercept + slope * panel["u"]
            total.append(_logistic(panel["u"], alpha, beta, width, b_pred - b_ref) - panel["share"])
        return np.concatenate(total)

    solved = least_squares(residual, np.asarray([100.0, 0.0, 30.0]),
                           bounds=([-600.0, -200.0, 5.0], [900.0, 200.0, 400.0]),
                           method="trf", xtol=1e-12, ftol=1e-12)
    return {"params": [float(v) for v in solved.x],
            "b_of_u": {"slope_mm_per_um": float(slope), "intercept_mm": float(intercept)}}


def _floor(panel: dict, model: str, fit: dict) -> float:
    a0, a1, w = fit["params"]
    if model == "M2":
        predicted = _logistic(panel["u"], a0, a1, w, panel["b"] - fit["b_ref_mm"])
    else:
        b_pred = fit["b_of_u"]["intercept_mm"] + fit["b_of_u"]["slope_mm_per_um"] * panel["u"]
        predicted = _logistic(panel["u"], a0, a1, w, b_pred - fit["b_ref_mm"])
    return float(np.sqrt(np.mean((predicted - panel["share"]) ** 2)))


def main() -> int:
    calibration = [_panel(route, truth) for route, truth in diagnosis.RUNS.values()]
    holdout = _panel(HOLDOUT, diagnosis._random_profile)

    # (1) Is the law's residual explained by the width offset at all?
    correlations = {}
    for panel in calibration + [holdout]:
        if panel["law_residual"].size >= 8:
            correlations[panel["route"]] = float(np.corrcoef(panel["law_residual"], panel["db"])[0, 1])

    # (2) Held-out test that keeps the law: remove the width term fitted on the calibration runs only.
    db = np.concatenate([panel["db"] for panel in calibration])
    residual = np.concatenate([panel["law_residual"] for panel in calibration])
    slope = float(np.sum(db * residual) / np.sum(db * db)) if float(np.sum(db * db)) > 0 else 0.0
    corrected = holdout["law_residual"] - slope * holdout["db"]
    floor_after = float(np.sqrt(np.mean(corrected ** 2)))
    relative_gain = 1.0 - floor_after / holdout["law_floor"] if holdout["law_floor"] > 0 else 0.0

    # (3) For the record: the crude two-coordinate logistic, which is NOT the fair test.
    two = _fit_two_coordinate(calibration)
    one = _fit_one_coordinate(calibration, two)
    one["b_ref_mm"] = two["b_ref_mm"]
    logistic_rows = [{"route": panel["route"], "M2_floor": _floor(panel, "M2", two),
                      "M3_floor": _floor(panel, "M3", one)} for panel in calibration + [holdout]]

    width_gain = floor_after <= FLOOR_TARGET
    if width_gain:
        verdict = ("the width carries the residual: removing a width term fitted on the calibration runs "
                   "brings the held-out floor to the target, so an independent width observation is the "
                   "missing input")
    elif relative_gain >= 0.30:
        verdict = ("the width explains part of the residual but not enough: the held-out floor improves "
                   "without reaching the target, so the per-station coupling still has to be re-derived")
    else:
        verdict = ("the width does not explain the spread of the residual: removing it changes the "
                   "held-out floor by less than 30 %, so the missing physics is not the contact width and "
                   "the per-station assumption itself has to be re-derived from the contact layer")

    payload = {"calibration_runs": [panel["route"] for panel in calibration], "holdout": HOLDOUT,
               "floor_target": FLOOR_TARGET,
               "rows": [{"route": panel["route"], "usable": panel["usable"],
                         "law_floor": panel["law_floor"],
                         "db_mm_range": [float(np.min(panel["db"])), float(np.max(panel["db"]))],
                         "corr_residual_vs_db": correlations.get(panel["route"])}
                        for panel in calibration + [holdout]],
               "width_correction": {"slope_share_per_mm": slope, "held_out_floor_before": holdout["law_floor"],
                                    "held_out_floor_after": floor_after,
                                    "relative_gain": relative_gain,
                                    "reaches_target": bool(width_gain)},
               "crude_logistic_appendix": {"note": ("a three-parameter logistic is a worse base than the "
                                                    "empirical law, so these numbers cannot decide anything "
                                                    "about the width; they are kept for the record"),
                                           "two_coordinate_fit": two, "one_coordinate_fit": one,
                                           "rows": logistic_rows},
               "verdict": verdict}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'run':28s} {'usable':>7s} {'law floor':>10s} {'db range (mm)':>18s} {'corr(r,db)':>11s}")
    for row in payload["rows"]:
        corr = row["corr_residual_vs_db"]
        print(f"{row['route']:28s} {row['usable']:7d} {row['law_floor']:10.4f}"
              f" {row['db_mm_range'][0]:8.3f} .. {row['db_mm_range'][1]:6.3f}"
              f" {('-' if corr is None else f'{corr:11.3f}')}")
    print(f"width correction fitted on calibration: {slope:+.5f} share per mm")
    print(f"held out {HOLDOUT}: before {holdout['law_floor']:.4f}  after {floor_after:.4f}"
          f"  gain {100*relative_gain:5.1f} %   target {FLOOR_TARGET}")
    print(f"appendix (crude logistic, not decisive): "
          + "  ".join(f"{row['route']} M2 {row['M2_floor']:.4f}" for row in logistic_rows))
    print(f"VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
