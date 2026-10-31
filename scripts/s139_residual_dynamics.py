"""M8 step 10: is the residual a dynamic effect, or does the quasi-static split really fail?

Round 281 rejected the no-fit point-Hertz split, and its own un-bumped run failed first, so the surviving
question is not "which second coordinate" but "is the measured share even a function of the station".

Every law in rounds 251-281 is quasi-static: it maps a station's gap to a share and assumes the wheel sits
at that station's equilibrium.  But the runs are 0.6 s of dynamics at 80 km/h, and a 0.35 m feature passes in
16 ms, which is shorter than the wheel's own vertical period.  So the share at a station can carry a
dynamic part that no static law can reproduce.

This module measures that directly, on archived runs only:

  1. predicted share = law(u0 + truth) at each frame's station            (the round-277 forward)
  2. residual r = predicted - measured, per frame
  3. spectrum of r over the observable window, and the energy split below / above 20 Hz
  4. cross-correlation lag between predicted and measured share, in mm of station

Pre-registered reading:

  dynamics  if more than 30 % of the residual energy sits above 20 Hz, or the peak lag exceeds 5 mm
  static    otherwise, i.e. the residual is a static modelling error and the quasi-static laws are the
            right family, so the next candidate stays a per-station contact model
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

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "residual_dynamics.json"
FIT_LO_M, FIT_HI_M = 57.5, 63.5
MODE_FREQUENCY_HZ = 20.0
ENERGY_FRACTION = 0.30
LAG_LIMIT_MM = 5.0


def _quasi_static_residual(route: str, truth_of) -> dict:
    loaded = base._load(base._run_id(route))
    station = np.asarray(loaded["station"], dtype=float)
    share = base._split(loaded)
    null = two_peak._null_state()
    build_law_result = assembly.build_law()
    sigma_of = joint.share_law(build_law_result)
    widths = law._width_at(station, *law._width_table())
    u0 = np.interp(station, null["stations"], null["u0"], left=np.nan, right=np.nan)
    truth = np.asarray(truth_of(station), dtype=float)
    predicted = sigma_of(u0 + truth, widths)
    usable = (np.isfinite(predicted) & np.isfinite(share) & (share > 0.02) & (share < 0.98)
              & (station >= FIT_LO_M) & (station <= FIT_HI_M))
    return {"route": route, "station": station[usable], "share": share[usable],
            "predicted": predicted[usable], "residual": (predicted - share)[usable],
            "times": np.asarray(loaded["times"], dtype=float)[usable],
            "speed_m_s": base.SPEED_KMH / 3.6}


def _spectrum(panel: dict) -> dict:
    residual = panel["residual"] - np.mean(panel["residual"])
    times = panel["times"]
    step = float(np.median(np.diff(times)))
    frequencies = np.fft.rfftfreq(residual.size, d=step)
    power = np.abs(np.fft.rfft(residual)) ** 2
    total = float(np.sum(power[1:]))
    if total <= 0.0:
        return {"step_s": step, "total": 0.0, "above_fraction": 0.0, "peak_hz": 0.0}
    above = float(np.sum(power[frequencies > MODE_FREQUENCY_HZ]))
    peak = float(frequencies[1 + int(np.argmax(power[1:]))])
    return {"step_s": step, "total": total, "above_fraction": above / total, "peak_hz": peak}


def _lag_mm(panel: dict) -> float:
    """Station lag that maximises the correlation between prediction and measurement."""
    predicted = panel["predicted"] - np.mean(panel["predicted"])
    measured = panel["share"] - np.mean(panel["share"])
    correlation = np.correlate(predicted, measured, mode="full")
    lags = np.arange(-measured.size + 1, predicted.size)
    best = int(lags[int(np.argmax(correlation))])
    spacing = float(np.median(np.diff(panel["station"])))
    return float(best * spacing * 1e3)


def main() -> int:
    panels = [_quasi_static_residual(route, truth) for route, truth in diagnosis.RUNS.values()]
    holdout = _quasi_static_residual("one_set_random", diagnosis._random_profile)
    rows = []
    for panel in panels + [holdout]:
        spectrum = _spectrum(panel)
        lag = _lag_mm(panel) if panel["residual"].size > 32 else float("nan")
        rows.append({"route": panel["route"], "usable": int(panel["residual"].size),
                     "residual_rms": float(np.sqrt(np.mean(panel["residual"] ** 2))),
                     "above_20hz_fraction": spectrum["above_fraction"],
                     "peak_hz": spectrum["peak_hz"], "lag_mm": lag})

    hold = rows[-1]
    dynamic = hold["above_20hz_fraction"] > ENERGY_FRACTION or abs(hold["lag_mm"]) > LAG_LIMIT_MM
    verdict = ("the residual is dynamic: a quasi-static law cannot reproduce it, so the next candidate is "
               "the wheel's vertical motion across the feature, not another static coordinate"
               if dynamic else
               "the residual is static: its energy sits below 20 Hz and the peak lag is within a few mm, so "
               "the quasi-static family is right and the next candidate stays a per-station contact model")
    payload = {"mode_frequency_hz": MODE_FREQUENCY_HZ, "energy_fraction_limit": ENERGY_FRACTION,
               "lag_limit_mm": LAG_LIMIT_MM, "rows": rows,
               "holdout_is_dynamic": bool(dynamic), "verdict": verdict}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'run':26s} {'usable':>7s} {'rms':>7s} {'>20Hz':>7s} {'peak Hz':>8s} {'lag mm':>7s}")
    for row in rows:
        print(f"{row['route']:26s} {row['usable']:7d} {row['residual_rms']:7.4f}"
              f" {row['above_20hz_fraction']:7.3f} {row['peak_hz']:8.1f} {row['lag_mm']:7.2f}")
    print(f"hold-out dynamic: {'YES' if dynamic else 'NO'}")
    print(f"VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
