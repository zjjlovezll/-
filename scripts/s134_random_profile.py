"""M8 step 5: a random profile -- a non-parametric estimator, and the parametric one for contrast.

Rounds 273-276 could size a profile because it was a handful of declared bumps.  A random irregularity
is not a handful: the count is neither known nor meaningful, so the estimator has to be
non-parametric.  This script builds one (seeded, therefore reproducible) and runs two estimators
against the same measured share:

    non-parametric   one unknown height per usable station, forward through the measured law, with a
                     second-difference smoothness penalty (declared before running: LAMBDA = 1.0e-4,
                     i.e. a weight of 0.01 share per um of curvature)
    parametric       the round-276 pipeline: count with the composable forward (BIC over K), then size
                     with the measured law at that count

Pre-registered, before running:

    G-ABS   p95 of the estimated profile <= 22 um where |truth| >= 10 % of its peak
    G-NULL  the same estimator applied to the un-bumped run gives p95 <= 16.7 um (= 1/3 of the
            smallest amplitude in this profile)
    G-CORR  correlation between estimate and truth >= 0.90 over the window
    G-PEAK  the largest true peak is located within 0.20 m
    G-RES   share residual rms <= 0.02 (the non-composition floor measured in round 274 was 0.0165)

None of these relaxes an earlier gate; G-CORR / G-PEAK / G-RES only add information.
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
import s131_peak_count as count_stage  # noqa: E402
import s132_composable_forward as forward  # noqa: E402
import s133_two_stage as two_stage  # noqa: E402

CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s134"
TRUTH_PATH = OUT / "truth.json"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "random_profile.json"
ROUTE = "one_set_random"

SEED = 20261031
PEAK_COUNT = 6
WIDTH_M = 0.35
CENTRE_LO_M, CENTRE_HI_M = 58.8, 62.4
MIN_SEPARATION_M = 0.45
AMPLITUDE_LO_UM, AMPLITUDE_HI_UM = 15.0, 45.0

SPEED_KMH = 80.0
DURATION_S = 0.6
FIT_LO_M, FIT_HI_M = 57.5, 63.5
WINDOW_FRACTION = 0.10
LAMBDA = 1.0e-4
Z_LO_UM, Z_HI_UM = -300.0, 400.0

ABSOLUTE_LIMIT_UM = assembly.ABSOLUTE_LIMIT_UM      # 22
NULL_LIMIT_UM = 16.7
CORRELATION_LIMIT = 0.90
PEAK_LIMIT_M = assembly.STATION_LIMIT_M            # 0.20
RESIDUAL_LIMIT = 0.02


def truth_peaks() -> list[tuple[float, float]]:
    """Seeded centres and amplitudes, kept inside the observable band."""
    rng = np.random.default_rng(SEED)
    centres: list[float] = []
    while len(centres) < PEAK_COUNT:
        candidate = float(rng.uniform(CENTRE_LO_M, CENTRE_HI_M))
        if all(abs(candidate - other) >= MIN_SEPARATION_M for other in centres):
            centres.append(candidate)
    centres.sort()
    amplitudes = rng.uniform(AMPLITUDE_LO_UM, AMPLITUDE_HI_UM, PEAK_COUNT)
    return [(centre, float(amplitude)) for centre, amplitude in zip(centres, amplitudes)]


def profile_um(stations: np.ndarray) -> np.ndarray:
    """The random surface: sum of the Gaussian components, in um."""
    return sum(amplitude * np.exp(-0.5 * ((stations - centre) / WIDTH_M) ** 2)
               for centre, amplitude in truth_peaks())


def build() -> int:
    peaks = truth_peaks()
    case = json.loads(CASE.read_text(encoding="utf-8"))
    touched = 0
    for template in case["rail_templates"]:
        for body in template.get("bodies", []):
            if body.get("id") != "blade":
                continue
            for station in body["stations"]:
                s_m = float(station["s_m"])
                height = float(profile_um(np.asarray([s_m]))[0]) * 1e-6
                station["profile"]["z_offset_m"] = float(station["profile"].get("z_offset_m", 0.0)) + height
                touched += 1
    case["case_id"] = f"{case['case_id']}_{ROUTE}"
    case["purpose_detail"] = (case.get("purpose_detail", "")
                             + f" | random corrugation variant: {len(peaks)} components, seed {SEED}")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{ROUTE}.json"
    path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    TRUTH_PATH.write_text(json.dumps({"seed": SEED, "width_m": WIDTH_M, "peaks": peaks},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"random profile: {len(peaks)} components, seed {SEED} -> {path.name} ({touched} blade stations)")
    for centre, amplitude in peaks:
        print(f"  {centre:8.3f} m  {amplitude:6.2f} um")
    return 0


def _grid_state(route: str) -> dict:
    """Measured share, null operating point, widths and stations for one run."""
    build_law_result = assembly.build_law()
    sigma_of = joint.share_law(build_law_result)
    null_state = two_peak._null_state()
    run = base._load(base._run_id(route))
    stations = np.asarray(run["station"], dtype=float)
    observed = base._smooth(base._split(run), stations, base.SMOOTH_M)
    null = np.full_like(stations, np.nan)
    for index, station in enumerate(null_state["stations"]):
        null[index] = null_state["u0"][index]
    widths = law._width_at(stations, *law._width_table())
    usable = (np.isfinite(observed) & np.isfinite(null) & (stations >= FIT_LO_M)
              & (stations <= FIT_HI_M) & (observed > joint.SHARE_LO) & (observed < joint.SHARE_HI))
    return {"station": stations, "observed": observed, "u0": null, "width": widths,
            "sigma_of": sigma_of, "usable": usable}


def invert_grid(state: dict, smooth_m: float = base.SMOOTH_M) -> dict:
    """One height per usable station, forward through the law, second-difference penalty."""
    stations = state["station"]
    usable = state["usable"]
    nodes = stations[usable]
    u0 = state["u0"][usable]
    widths = state["width"][usable]
    observed = state["observed"][usable]
    if nodes.size < 8:
        raise SystemExit("too few usable stations to invert")
    spacing = float(np.median(np.diff(nodes)))
    scale = 1.0 / (spacing ** 2)
    second = np.zeros((nodes.size - 2, nodes.size))
    for row in range(nodes.size - 2):
        second[row, row] = scale
        second[row, row + 1] = -2.0 * scale
        second[row, row + 2] = scale

    def residual(z_um: np.ndarray) -> np.ndarray:
        predicted = state["sigma_of"](u0 + z_um, widths)
        return np.concatenate([predicted - observed, np.sqrt(LAMBDA) * (second @ z_um)])

    solved = least_squares(residual, np.zeros(nodes.size),
                           bounds=(Z_LO_UM, Z_HI_UM), method="trf", xtol=1e-10, ftol=1e-10, max_nfev=400)
    return {"station": nodes, "z_um": solved.x,
            "share_rms": float(np.sqrt(np.mean((state["sigma_of"](u0 + solved.x, widths) - observed) ** 2))),
            "spacing_m": spacing}


def _sample(stations: np.ndarray, nodes: np.ndarray, values: np.ndarray) -> np.ndarray:
    order = np.argsort(nodes)
    return np.interp(stations, nodes[order], values[order])


def judge(estimate_station: np.ndarray, estimate_um: np.ndarray, share_rms: float,
          truth: np.ndarray | None = None) -> dict:
    """Score an estimate against the seeded profile, or against zero for the null run.

    The null run has no profile to recover, so judging it against the seeded one would be wrong: it is
    scored against zero over every usable station, which is what the G-NULL limit was defined for.
    """
    if truth is None:
        truth = profile_um(estimate_station)
    else:
        truth = np.asarray(truth, dtype=float)
    if np.allclose(truth, 0.0):
        window = np.ones_like(truth, dtype=bool)
    else:
        window = np.abs(truth) >= WINDOW_FRACTION * float(np.max(np.abs(truth)))
    difference = estimate_um[window] - truth[window]
    p95 = float(np.percentile(np.abs(difference), 95))
    correlation = float(np.corrcoef(estimate_um[window], truth[window])[0, 1])
    peak_index = int(np.argmax(np.abs(truth)))
    peak_station = float(estimate_station[peak_index])
    near = np.abs(estimate_station - peak_station) <= 0.6
    if near.any():
        found = float(estimate_station[near][int(np.argmax(np.abs(estimate_um[near])))])
        peak_error = abs(found - peak_station)
    else:
        peak_error = float("inf")
    gates = {"G-ABS": p95 <= ABSOLUTE_LIMIT_UM, "G-CORR": correlation >= CORRELATION_LIMIT,
             "G-PEAK": peak_error <= PEAK_LIMIT_M, "G-RES": share_rms <= RESIDUAL_LIMIT}
    return {"p95_um": p95, "correlation": correlation, "peak_error_m": peak_error,
            "share_rms": share_rms, "window_stations": int(window.sum()),
            "gates": gates, "passed": bool(all(gates.values()))}


def parametric(state: dict) -> dict:
    """The round-276 pipeline on the same run: count with the composable forward, size with the law.

    The count loops K = 1..PEAK_COUNT (the composable forward is closed-form, so this is cheap); the
    selection is by BIC exactly as in round 275, and the sizing is round 276's joint step at that K.
    """
    rich = count_stage.observed_state(ROUTE)
    stiffness = forward.fit_stiffness()
    composable = forward._state(ROUTE)
    composable = dict(composable, u0=rich["u0"], widths=rich["widths"])
    bics: dict[int, float] = {}
    fits: dict[int, dict] = {}
    for count in range(1, PEAK_COUNT + 1):
        fitted = forward.fit_count(composable, count, stiffness["c_stock"], stiffness["c_blade"])
        fits[count] = fitted
        bics[count] = float(fitted["bic"])
    selected = min(bics, key=bics.get)
    sized = two_stage.stage_two_joint(rich, [[centre, amplitude] for centre, amplitude in fits[selected]["peaks"]])
    estimate = np.zeros_like(state["station"])
    for centre, amplitude in sized["peaks"]:
        estimate = estimate + amplitude * np.exp(-0.5 * ((state["station"] - centre) / WIDTH_M) ** 2)
    return {"selected": int(selected), "bic": {str(key): value for key, value in bics.items()},
            "stiffness": stiffness, "counted_peaks": fits[selected]["peaks"],
            "peaks": sized["peaks"], "estimate_um": estimate, "sized": True}


def report() -> int:
    state = _grid_state(ROUTE)
    grid = invert_grid(state)
    grid_result = judge(grid["station"], grid["z_um"], grid["share_rms"])

    null_state = _grid_state(assembly.BASELINE_ROUTE)
    null_grid = invert_grid(null_state)
    null_judged = judge(null_grid["station"], null_grid["z_um"], null_grid["share_rms"],
                        truth=np.zeros_like(null_grid["station"]))
    null_p95 = null_judged["p95_um"]

    # How well CAN any estimator do on this run?  Predict the measured share forward from the seeded
    # truth through the same law: that residual is the floor an estimator cannot pass, and it separates
    # "the estimator is weak" from "the law cannot represent this profile".
    truth_um = profile_um(state["station"][state["usable"]])
    predicted = state["sigma_of"](state["u0"][state["usable"]] + truth_um, state["width"][state["usable"]])
    floor = predicted - state["observed"][state["usable"]]
    floor_rms = float(np.sqrt(np.mean(floor ** 2)))
    truth_max = float(np.max(np.abs(truth_um)))
    saturated = float(np.mean(predicted >= 0.999))
    observed_max = float(np.max(state["observed"][state["usable"]]))

    parametric_result = parametric(state)
    parametric_judged = None
    if parametric_result["peaks"]:
        parametric_judged = judge(state["station"], parametric_result["estimate_um"],
                                  float("nan"))
        parametric_judged["share_rms"] = float("nan")

    gates_all = dict(grid_result["gates"])
    gates_all["G-NULL"] = null_p95 <= NULL_LIMIT_UM
    passed = bool(all(gates_all.values()))
    payload = {
        "route": ROUTE, "run_id": base._run_id(ROUTE), "truth": truth_peaks(), "seed": SEED,
        "width_m": WIDTH_M, "lambda": LAMBDA,
        "non_parametric": {**grid_result, "usable_stations": int(state["usable"].sum()),
                           "spacing_m": grid["spacing_m"]},
        "null": {"p95_um": null_p95, "gates": null_judged["gates"]},
        "composition_floor": {"share_rms": floor_rms,
                              "truth_max_um": truth_max,
                              "saturated_fraction": saturated,
                              "observed_share_max": observed_max,
                              "passed": floor_rms <= RESIDUAL_LIMIT,
                              "note": ("the measured law cannot represent this profile better than "
                                       "this residual, so it bounds every estimator built on it")},
        "parametric": {"selected": parametric_result["selected"], "bic": parametric_result["bic"],
                       "peaks": parametric_result["peaks"], "judged": parametric_judged},
        "gates": gates_all, "passed": passed,
        "verdict": ("the random profile is recovered within the absolute gate" if passed else
                    "the random profile is not recovered to the absolute gate; the numbers are reported as they are"),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"run {payload['run_id']}  usable {payload['non_parametric']['usable_stations']} stations"
          f"  spacing {grid['spacing_m']*1000:.0f} mm")
    print(f"non-parametric  p95 {grid_result['p95_um']:8.2f} um  corr {grid_result['correlation']:.3f}"
          f"  peak err {grid_result['peak_error_m']*1000:6.1f} mm  share rms {grid['share_rms']:.4f}")
    print(f"null            p95 {null_p95:8.2f} um (limit {NULL_LIMIT_UM})")
    print(f"law floor       share rms {floor_rms:.4f} (limit {RESIDUAL_LIMIT}) "
          f"-- what the measured law can do on THIS profile")
    print(f"                truth max {truth_max:6.1f} um   saturated stations {100*saturated:5.1f} %"
          f"   observed share max {observed_max:.3f}")
    print(f"parametric      selected K {parametric_result['selected']} of {PEAK_COUNT} true components")
    if parametric_judged is not None:
        print(f"                p95 {parametric_judged['p95_um']:8.2f} um  corr "
              f"{parametric_judged['correlation']:.3f}  peak err "
              f"{parametric_judged['peak_error_m']*1000:6.1f} mm")
    for name, value in gates_all.items():
        print(f"  {name:7s} {'PASS' if value else 'FAIL'}")
    print(f"VERDICT: {payload['verdict']}")
    return 0


def main(argv: list[str]) -> int:
    if "--build" in argv:
        return build()
    return report()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
