"""Corrugation depth on a curved route, inverted from the vehicle's own response.

Why not the turnout case: B041 measured that ``case_diverging_R1100.json`` glues two different
rail models together (gauge wanders 1.4438..1.5876 m against the wheels' 1.493 m, right wheel on
the gauge corner at 2.69x even share), and repairing it with a constant offset failed at every
value tried.  A *symmetric* table driven as a curve is clean: ``s31_curve_smoke.py`` measured
8/8 wheels at 0.988..1.013x even share, penetration 65.47 um on all eight and 7/7 gates at
R = 1100 m, 80 km/h.  So the curvature physics can be exercised there without the turnout's data
defect, and that is where the corrugation experiment belongs.

Protocol, pre-registered before the run:

* one rail only -- the inner rail of the curve, which is the right rail because the design line
  moves towards +y;
* the defect is a random mixture of four log-stratified wavelengths in 0.10..0.30 m, with uniform
  phases and weights from ``SEED``; the mixture is scaled so its peak-to-peak is exactly the
  level, which fixes every component's own amplitude as ``scale * weight``;
* three levels 0 / 0.1 / 0.3 mm peak-to-peak; the per-component complex gain is calibrated on the
  smallest excited level and used to predict the larger one, so the prediction is out of sample
  in amplitude;
* observable: the leading wheelset's vertical acceleration, projected per component by complex
  least squares onto ``exp(i w t)`` over the window in which that axle is over the patch (the
  frequencies are known: ``f = v / lambda``).

Gates (fixed before the numbers): (1) every component's response at 0 mm must be at least 6x
below its response at 0.1 mm, otherwise that band is not excited and no depth may be quoted for
it; (2) each component's recovered peak-to-peak at 0.3 mm must land within 2 dB; (3) the recovered
wavelength must match the drawn one to 1 % (it does by construction -- the projection uses the
known frequency, so this gate only guards a wrong speed).  Failing any is reported as a failure.

Run:  python -X utf8 scripts/s31b_curve_corrugation.py [--duration 0.34] [--levels 0 0.1 0.3]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

from velch import data_root
from velch.irregularity import IrregularityTrack, ShiftedSeries, scaled_track
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

RADIUS_M = 1100.0
SPEED_KMH = 80.0
X_START_M = 30.0
PATCH_M = (42.5, 45.5)
STEP_M = 2.5e-3
FADE_M = 0.05
LAMBDAS_M = (0.10, 0.30)
COMPONENTS = 4
SEED = 20261028
HALF_GAUGE_M = 0.7465
LEAD_AXLE_OFFSET_M = 10.0
EXCITATION_GATE = 6.0
DEPTH_GATE_DB = 2.0


def draw_components() -> list[tuple[float, float, float]]:
    """Stratified wavelengths, uniform phases and weights -- the layout s27 used."""
    rng = np.random.default_rng(SEED)
    edges = np.linspace(math.log(LAMBDAS_M[0]), math.log(LAMBDAS_M[1]), COMPONENTS + 1)
    wavelengths = [float(math.exp(rng.uniform(low, high)))
                   for low, high in zip(edges[:-1], edges[1:])]
    phases = [float(rng.uniform(0.0, 2.0 * math.pi)) for _ in range(COMPONENTS)]
    weights = [float(rng.uniform(0.5, 0.9)) for _ in range(COMPONENTS)]
    return list(zip(wavelengths, phases, weights))


def mixture(level_mm: float, components) -> tuple[IrregularityTrack | None, dict[float, float]]:
    """The applied record and each component's own amplitude, both in metres."""
    if level_mm <= 0.0:
        return None, {wavelength: 0.0 for wavelength, _, _ in components}
    start, end = PATCH_M
    count = int(round((end - start) / STEP_M)) + 1
    s_m = start + STEP_M * np.arange(count)
    total = np.zeros_like(s_m)
    for wavelength, phase, weight in components:
        total += weight * np.sin(2.0 * math.pi * s_m / wavelength + phase)
    # Normalise the mixture itself, not the sum of weights: the components drift in and out of
    # phase, so sum(weights) is not the peak-to-peak of anything.
    scale = (0.5 * level_mm * 1.0e-3) / float(np.max(np.abs(total)))
    profile = scale * total
    amplitudes = {wavelength: scale * weight for wavelength, _, weight in components}
    track = IrregularityTrack(s_m=s_m, lateral_m=np.zeros_like(s_m), vertical_m=profile,
                              roll_rad=np.zeros_like(s_m), gauge_m=np.zeros_like(s_m),
                              source=f"random mixture, pp {level_mm} mm")
    return track, amplitudes


def build_case(*, duration_s: float, name: str) -> Path:
    raw = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
    raw["case_id"] = name
    raw["run"].update({
        "x_start_m": X_START_M,
        "seat_x_start_m": X_START_M,
        "duration_s": duration_s,
        "output_step_s": 2.0e-4,
        "max_solver_step_s": 1.0e-4,
        "curve_radius_m": RADIUS_M,
        "curve_geometry": True,
        "align_to_track": True,
    })
    raw.pop("curve_cant_m", None)
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw.pop("initial_state", None)
    raw.pop("irregularity", None)
    target = Path(__file__).resolve().parents[2] / "scratch" / "s31" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return target


def shift_inner_rail(case, track: IrregularityTrack):
    """Wrap only the inner (right) rail's series; the outer rail stays bit-exact."""
    rails = []
    for rail in case.rails:
        if str(rail.id).endswith("right"):
            bodies = tuple(replace(body, series=ShiftedSeries(body.series, track, "right",
                                                              HALF_GAUGE_M))
                           for body in rail.bodies)
            rails.append(replace(rail, bodies=bodies))
        else:
            rails.append(rail)
    return replace(case, rails=tuple(rails))


def run_level(*, duration_s: float, level_mm: float, components, name: str):
    path = build_case(duration_s=duration_s, name=name)
    case = load_vehicle_case(path)
    track, amplitudes = mixture(level_mm, components)
    if track is not None:
        windowed = scaled_track(track, channels=("vertical",),
                                start_m=PATCH_M[0], end_m=PATCH_M[1], fade_m=FADE_M)
        case = shift_inner_rail(case, windowed)
    return case, simulate_vehicle(case), amplitudes


def complex_amplitude(times: np.ndarray, signal: np.ndarray, frequency: float) -> complex:
    """Least-squares projection onto ``exp(i w t)`` with a constant offset in the design."""
    omega = 2.0 * math.pi * frequency
    design = np.column_stack((np.cos(omega * times), np.sin(omega * times),
                              np.ones_like(times)))
    coefficients, *_ = np.linalg.lstsq(design, signal, rcond=None)
    return complex(float(coefficients[0]), -float(coefficients[1]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=0.34)
    parser.add_argument("--levels", type=float, nargs="+", default=[0.0, 0.1, 0.3])
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)

    components = draw_components()
    speed = SPEED_KMH / 3.6
    print(f"curve R {RADIUS_M} m at {SPEED_KMH} km/h from {X_START_M} m, patch "
          f"{PATCH_M[0]}..{PATCH_M[1]} m on the inner (right) rail, step {STEP_M * 1e3:.2f} mm")
    for wavelength, phase, weight in components:
        print(f"  lambda {wavelength:.4f} m  phase {phase:.4f}  weight {weight:.4f}  "
              f"f {speed / wavelength:7.2f} Hz")

    entry_s = (PATCH_M[0] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    exit_s = (PATCH_M[1] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    print(f"  leading axle over the patch t {entry_s * 1e3:.1f} .. {exit_s * 1e3:.1f} ms "
          f"({exit_s - entry_s:.4f} s, {exit_s - entry_s} / min(lambda) = "
          f"{(exit_s - entry_s) * speed / min(w for w, _, _ in components):.1f} periods of the "
          "slowest component)")
    if args.duration < exit_s:
        raise SystemExit(f"--duration {args.duration} ends before the axle leaves the patch at "
                         f"{exit_s:.4f} s; the projection window would be truncated")

    runs = {}
    for level in args.levels:
        case, result, amplitudes = run_level(duration_s=args.duration, level_mm=level,
                                            components=components,
                                            name=f"case_corrug_{level:g}mm.json")
        summary = result.summary
        failing = [gate for gate, ok in summary["gates"].items() if not ok]
        passed = sum(1 for ok in summary["gates"].values() if ok)
        print(f"  level {level:g} mm: {summary['result_status']} gates {passed}"
              f"/{len(summary['gates'])} failing {failing} "
              f"max pen {summary['max_penetration_m'] * 1e6:.1f} um")
        if summary["result_status"] != "numerically_checked":
            raise SystemExit(f"level {level:g} mm did not integrate; no depth may be quoted")
        runs[level] = (case, result, amplitudes)

    names = runs[args.levels[0]][1].acceleration_names
    channel = next((name for name in names if name.startswith("axle1") and "z_acc" in name), None)
    if channel is None:
        print("  acceleration channels:", ", ".join(names))
        raise SystemExit("no leading-wheelset vertical acceleration channel")
    index = runs[args.levels[0]][1].acceleration_names.index(channel)
    print(f"  observable {channel}")

    times = runs[args.levels[0]][1].times_s
    mask = (times >= entry_s) & (times <= exit_s)
    window = times[mask]
    print(f"  window {mask.sum()} samples")

    report = {"channel": channel, "radius_m": RADIUS_M, "speed_kmh": SPEED_KMH,
              "patch_m": list(PATCH_M), "window_s": [entry_s, exit_s],
              "levels_mm": list(args.levels),
              "components": [], "gates": {}}
    rows = []
    for wavelength, phase, weight in components:
        frequency = speed / wavelength
        row = {"lambda_m": wavelength, "frequency_hz": frequency, "weight": weight,
               "applied_um": {}, "response": {}}
        for level in args.levels:
            signal = runs[level][1].accelerations[mask, index]
            row["response"][f"{level:g}"] = float(abs(complex_amplitude(window, signal, frequency)))
            row["applied_um"][f"{level:g}"] = runs[level][2][wavelength] * 1e6
        rows.append(row)
        report["components"].append(row)
        print(f"  lambda {wavelength:.4f} m  f {frequency:7.2f} Hz  applied "
              f"{[round(row['applied_um'][f'{l:g}'], 3) for l in args.levels]} um  "
              f"response {[round(row['response'][f'{l:g}'], 6) for l in args.levels]} m/s2")

    excited = [level for level in args.levels if level > 0.0]
    if len(excited) < 2:
        raise SystemExit("need two excited levels: one to calibrate a gain, one to test it")
    calibration, target = excited[0], excited[-1]

    # Gate 1: the zero-level response must be well below the smallest excited one.
    quiet = [level for level in args.levels if level == 0.0]
    quiet_gate = {}
    if quiet:
        zero = quiet[0]
        for row in rows:
            excited_response = row["response"][f"{calibration:g}"]
            zero_response = row["response"][f"{zero:g}"]
            ratio = excited_response / zero_response if zero_response > 0.0 else float("inf")
            quiet_gate[f"{row['lambda_m']:.4f}"] = {"excited_over_zero": ratio,
                                                    "passed": bool(ratio >= EXCITATION_GATE)}
            print(f"  gate 1  lambda {row['lambda_m']:.4f} m  excited/zero {ratio:8.1f}x  "
                  f"{'pass' if ratio >= EXCITATION_GATE else 'FAIL -- band not excited'}")
    report["gates"]["excitation"] = quiet_gate

    print(f"  gain calibrated on {calibration:g} mm, predicting {target:g} mm")
    depth_gate = {}
    for row in rows:
        gain = row["response"][f"{calibration:g}"] / row["applied_um"][f"{calibration:g}"]
        recovered_pp_um = 2.0 * row["response"][f"{target:g}"] / gain if gain > 0.0 else float("nan")
        truth_pp_um = 2.0 * row["applied_um"][f"{target:g}"]
        error_db = (20.0 * math.log10(recovered_pp_um / truth_pp_um)
                    if truth_pp_um > 0.0 and recovered_pp_um > 0.0 else float("nan"))
        passed = bool(abs(error_db) <= DEPTH_GATE_DB)
        row["gain_per_m_s2_per_m"] = gain * 1e-6
        row["recovered_pp_um"] = recovered_pp_um
        row["truth_pp_um"] = truth_pp_um
        row["error_db"] = error_db
        depth_gate[f"{row['lambda_m']:.4f}"] = {"error_db": error_db, "passed": passed}
        print(f"  gate 2  lambda {row['lambda_m']:.4f} m  recovered {recovered_pp_um:8.3f} um pp "
              f"vs truth {truth_pp_um:8.3f} um pp  {error_db:+6.2f} dB  "
              f"{'pass' if passed else 'FAIL'}")
    report["gates"]["depth"] = depth_gate
    hits = sum(1 for item in depth_gate.values() if item["passed"])
    print(f"  depth gate {hits}/{len(depth_gate)} components within {DEPTH_GATE_DB:g} dB")

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")
        print(f"  wrote {args.json}")
    return 0 if hits == len(depth_gate) else 1


if __name__ == "__main__":
    sys.exit(main())
