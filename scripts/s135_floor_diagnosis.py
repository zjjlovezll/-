"""M8 step 6: is the round-277 floor a real composition error, or the law's u-range clamping?

Round 277 measured the representation error of the measured share law on a six-component random profile:
share rms 0.1314, against 0.0165 on the two-peak profile.  That number decided the next step ("fix the
forward"), so it has to be attributed before anything is rebuilt.

The law is a lookup `sigma(u) -> share` read off a single-station sweep, and the lookup is clamped at
both ends (`left=1.0`, `right=0.0` in s124.share_law).  So a big raise can leave the measured u-range and
be answered with a saturated share even when the simulated share never saturates -- the same signature as
"the law does not compose", and this project has confused the two before (round 259: 16 mm was the strip
window, not the identifiable width).

This script separates them with no new simulation:

    clamped_fraction   how often the truth's u leaves the measured curve
    floor_all          the round-277 number, recomputed
    floor_unclamped    the same, over stations that stayed inside the curve

Pre-registered reading: if `floor_unclamped` is well below `floor_all` the floor is mostly a range
artefact and the fix is to extend the law, not to rebuild the contact layer.
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

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "floor_diagnosis.json"
FIT_LO_M, FIT_HI_M = 57.5, 63.5

RUNS = {
    "two_peak": ("one_set_twopeak", lambda s: 50.0 * np.exp(-0.5 * ((s - 57.6) / 0.35) ** 2)
                 + 30.0 * np.exp(-0.5 * ((s - 59.4) / 0.35) ** 2)),
    "three_peak": ("one_set_threepeak_obs", lambda s: 40.0 * np.exp(-0.5 * ((s - 58.5) / 0.35) ** 2)
                   + 30.0 * np.exp(-0.5 * ((s - 59.5) / 0.35) ** 2)
                   + 20.0 * np.exp(-0.5 * ((s - 60.5) / 0.35) ** 2)),
}


def _random_profile(stations: np.ndarray) -> np.ndarray:
    import s134_random_profile as random_profile
    return random_profile.profile_um(stations)


def diagnose(route: str, truth_of) -> dict:
    build_law_result = assembly.build_law()
    sigma_of = joint.share_law(build_law_result)
    curves, _ = law._measured_curves()
    anchor = build_law_result[2]
    curve_u, curve_sigma = curves[float(anchor["station_m"])]
    order = np.argsort(curve_u)
    u_lo, u_hi = float(curve_u[order][0]), float(curve_u[order][-1])

    null_state = two_peak._null_state()
    run = base._load(base._run_id(route))
    stations = np.asarray(run["station"], dtype=float)
    observed = base._smooth(base._split(run), stations, base.SMOOTH_M)
    widths = law._width_at(stations, *law._width_table())
    u0 = np.interp(stations, null_state["stations"], null_state["u0"], left=np.nan, right=np.nan)
    usable = (np.isfinite(observed) & np.isfinite(u0) & (stations >= FIT_LO_M) & (stations <= FIT_HI_M)
              & (observed > joint.SHARE_LO) & (observed < joint.SHARE_HI))
    if int(usable.sum()) < 8:
        raise SystemExit(f"{route}: too few usable stations")

    u = u0[usable] + np.asarray(truth_of(stations[usable]), dtype=float)
    share = observed[usable]
    predicted = sigma_of(u, widths[usable])
    error = predicted - share
    low = u < u_lo
    high = u > u_hi
    inside = ~(low | high)
    return {
        "route": route, "run_id": base._run_id(route), "usable": int(usable.sum()),
        "curve_u_range": [u_lo, u_hi],
        "u_min": float(np.min(u)), "u_max": float(np.max(u)),
        "clamped_low": int(low.sum()), "clamped_high": int(high.sum()),
        "clamped_fraction": float(np.mean(low | high)),
        "floor_all": float(np.sqrt(np.mean(error ** 2))),
        "floor_unclamped": float(np.sqrt(np.mean(error[inside] ** 2))) if inside.any() else float("nan"),
        "unclamped": int(inside.sum()),
    }


def main() -> int:
    rows = [diagnose(route, truth) for route, truth in RUNS.values()]
    rows.append(diagnose("one_set_random", _random_profile))
    payload = {"curve_station_m": float(assembly.build_law()[2]["station_m"]), "runs": rows}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'run':28s} {'usable':>7s} {'clamped':>8s} {'floor_all':>10s} {'floor_in':>9s} {'in':>6s}")
    for row in rows:
        print(f"{row['route']:28s} {row['usable']:7d} {100*row['clamped_fraction']:7.1f}%"
              f" {row['floor_all']:10.4f} {row['floor_unclamped']:9.4f} {row['unclamped']:6d}")
    random_row = rows[-1]
    if random_row["clamped_fraction"] < 0.05:
        verdict = ("the floor is not a range artefact: the truth stays inside the measured u-range and "
                   "the law still misrepresents it, so the composition problem is real")
    elif random_row["floor_unclamped"] < 0.5 * random_row["floor_all"]:
        verdict = ("the floor is mostly a range artefact: most of it disappears on the stations that "
                   "stay inside the measured curve, so extend the law before rebuilding the contact layer")
    else:
        verdict = ("both effects are present: part of the floor is clamping and part survives inside "
                   "the curve")
    print(f"VERDICT: {verdict}")
    payload["verdict"] = verdict
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
