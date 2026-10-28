"""Is the amplitude-dependent transfer really a *preload* effect?

Context: `scripts/s35_straight_random_speed.py` measured that the transfer gain is not proportional
to the applied depth and that the drift points in opposite directions in different bands (0.1004 m
loses a factor of 8 between 0.1 and 0.3 mm peak-to-peak, 0.2293 m gains 1.6x), with the wheel never
leaving the rail (0.0 % of the window).  `scripts/s36b_contact_migration.py` then showed the contact
point does not migrate at all (lever_y constant to 1e-6 m over +-150 um of rail height), so the
geometry per se is not the source.

What is left is the Hertz law: F = C d^1.5, so the contact stiffens as sqrt(mean penetration).  A
bigger record raises the *mean* penetration, which raises the contact mode frequency, which moves
every band relative to that mode -- up on one side, down on the other.  That single mechanism
predicts the observed sign flip without any new physics.

This script tests it without changing the record's amplitude: the same 0.1 mm mixture, with the
whole left rail raised by 0 / 40 / 85 / 130 um, so the mean penetration steps through the same
range the amplitude sweep covered.  If the responses move the same way as they did with amplitude,
then the controlling variable is the mean contact preload and amplitude only acts through it --
which is testable, and it changes what an inversion has to condition on.

Usage:
    PYTHONPATH=src python -X utf8 scripts/s36c_preload_sweep.py
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np

from velch.irregularity import IrregularityTrack, ShiftedSeries
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

BASE_CASE = Path("F:/velch_data/validation/crh380a_m/case_A_final_law.json")
OUT_DIR = Path("../scratch/s36")
PATCH_M = (42.5, 45.5)
STEP_M = 5.0e-2
FADE_M = 0.5
LAMBDAS_M = (0.10, 0.30)
COMPONENTS = 4
SEED = 20261028
HALF_GAUGE_M = 0.7465
X_START_M = 30.0
LEAD_AXLE_OFFSET_M = 10.0
SPEED_KMH = 70.3206          # the draw s35 made, reused so the two sweeps are comparable
LEVEL_MM = 0.1
PRELOADS_UM = (0.0, 40.0, 85.0, 130.0)
ROUTE_M = (0.0, 150.0)


def components() -> list[tuple[float, float, float]]:
    rng = np.random.default_rng(SEED)
    edges = np.linspace(math.log(LAMBDAS_M[0]), math.log(LAMBDAS_M[1]), COMPONENTS + 1)
    wavelengths = [float(math.exp(rng.uniform(low, high)))
                   for low, high in zip(edges[:-1], edges[1:])]
    phases = [float(rng.uniform(0.0, 2.0 * math.pi)) for _ in range(COMPONENTS)]
    weights = [float(rng.uniform(0.5, 0.9)) for _ in range(COMPONENTS)]
    return list(zip(wavelengths, phases, weights))


def combined_track(preload_m: float, parts) -> tuple[IrregularityTrack, dict[float, float]]:
    """The 0.1 mm mixture inside its patch plus a smooth static step across the whole route."""
    start, end = PATCH_M
    s_m = ROUTE_M[0] + STEP_M * np.arange(int(round((ROUTE_M[1] - ROUTE_M[0]) / STEP_M)) + 1)
    vertical = np.zeros_like(s_m)

    # static step: zero at both ends of the route so the series bounds carry no jump
    low, high = ROUTE_M[0], ROUTE_M[1]
    ramp_in = np.clip((s_m - (low + 1.0)) / FADE_M, 0.0, 1.0)
    ramp_out = np.clip((high - 1.0 - s_m) / FADE_M, 0.0, 1.0)
    vertical += preload_m * np.minimum(ramp_in, ramp_out)

    inside = (s_m >= start) & (s_m <= end)
    patch_s = s_m[inside]
    total = np.zeros_like(patch_s)
    for wavelength, phase, weight in parts:
        total += weight * np.sin(2.0 * math.pi * patch_s / wavelength + phase)
    scale = (0.5 * LEVEL_MM * 1.0e-3) / float(np.max(np.abs(total)))
    vertical[inside] += scale * total
    amplitudes = {wavelength: scale * weight for wavelength, phase, weight in parts}

    track = IrregularityTrack(s_m=s_m, lateral_m=np.zeros_like(s_m), vertical_m=vertical,
                             roll_rad=np.zeros_like(s_m), gauge_m=np.zeros_like(s_m),
                             source=f"0.1 mm mixture on a {preload_m * 1e6:+.0f} um step")
    return track, amplitudes


def build_case(*, duration_s: float, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = json.loads(BASE_CASE.read_text(encoding="utf-8"))
    run = raw["run"]
    run["x_start_m"] = X_START_M
    run["duration_s"] = duration_s
    run["output_step_s"] = 5.0e-4
    run["max_solver_step_s"] = 5.0e-5
    run["method"] = "BDF"
    run["jacobian"] = "analytic"
    run["rtol"] = 1.0e-6
    run["atol"] = 1.0e-8
    run.pop("initial_state", None)
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw["id"] = f"s36c_{name}"
    raw["purpose"] = "synthetic"
    target = OUT_DIR / name
    target.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return target


def shift_left_rails(case, track: IrregularityTrack):
    rails = []
    for rail in case.rails:
        if str(rail.id).endswith("left"):
            bodies = tuple(replace(body, series=ShiftedSeries(body.series, track, "left",
                                                              HALF_GAUGE_M))
                           for body in rail.bodies)
            rails.append(replace(rail, bodies=bodies))
        else:
            rails.append(rail)
    return replace(case, rails=tuple(rails))


def complex_amplitude(times: np.ndarray, signal: np.ndarray, frequency: float) -> complex:
    omega = 2.0 * math.pi * frequency
    design = np.column_stack((np.cos(omega * times), np.sin(omega * times),
                              np.ones_like(times)))
    coefficients, *_ = np.linalg.lstsq(design, signal, rcond=None)
    return complex(float(coefficients[0]), -float(coefficients[1]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=0.30)
    parser.add_argument("--json", type=Path, default=OUT_DIR / "preload_sweep.json")
    args = parser.parse_args(argv)

    parts = components()
    speed = SPEED_KMH / 3.6
    entry_s = (PATCH_M[0] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    exit_s = (PATCH_M[1] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    print(f"straight route, {SPEED_KMH:.2f} km/h, {LEVEL_MM} mm mixture on the left rail, "
          f"window {entry_s:.4f}..{exit_s:.4f} s")
    if args.duration < exit_s:
        raise SystemExit("--duration ends before the axle leaves the patch")

    runs = {}
    for preload_um in PRELOADS_UM:
        path = build_case(duration_s=args.duration,
                          name=f"case_preload_{preload_um:.0f}um.json")
        case = load_vehicle_case(path)
        track, amplitudes = combined_track(preload_um * 1e-6, parts)
        case = shift_left_rails(case, track)
        result = simulate_vehicle(case)
        summary = result.summary
        failing = [gate for gate, ok in summary["gates"].items() if not ok]
        print(f"  preload {preload_um:+6.1f} um: {summary['result_status']} "
              f"gates {sum(summary['gates'].values())}/{len(summary['gates'])} "
              f"failing {failing} max pen {summary['max_penetration_m'] * 1e6:.2f} um")
        if summary["result_status"] != "numerically_checked":
            raise SystemExit(f"preload {preload_um} um did not integrate")
        runs[preload_um] = result

    times = runs[PRELOADS_UM[0]].times_s
    mask = (times >= entry_s) & (times <= exit_s)
    window = times[mask]
    names = runs[PRELOADS_UM[0]].acceleration_names
    channel = next(name for name in names if name.startswith("axle1") and "z_acc" in name)
    index = names.index(channel)
    print(f"  observable {channel}, window {int(mask.sum())} samples")

    # mean and peak penetration over the window, per preload
    penetration = {}
    for preload_um, result in runs.items():
        values = []
        for frame_index in np.nonzero(mask)[0]:
            response = result.contacts[frame_index].get("axle1_left")
            if response is not None and response.geometry is not None:
                values.append(response.geometry.penetration_m)
        penetration[preload_um] = (float(np.mean(values)) if values else 0.0,
                                  float(np.max(values)) if values else 0.0)
        print(f"  preload {preload_um:+6.1f} um: mean penetration "
              f"{penetration[preload_um][0] * 1e6:7.2f} um, max "
              f"{penetration[preload_um][1] * 1e6:7.2f} um")

    report = {"route": "straight", "speed_kmh": SPEED_KMH, "level_mm": LEVEL_MM,
              "preloads_um": list(PRELOADS_UM), "channel": channel, "bands": []}
    print("\n  lambda      f (Hz)   " + "  ".join(f"{p:+6.0f} um" for p in PRELOADS_UM)
          + "    ratio to the lowest preload")
    base = PRELOADS_UM[0]
    for wavelength, phase, weight in parts:
        frequency = speed / wavelength
        row = {"lambda_m": wavelength, "frequency_hz": frequency, "response": {}}
        for preload_um, result in runs.items():
            signal = result.accelerations[mask, index]
            row["response"][f"{preload_um:g}"] = float(
                abs(complex_amplitude(window, signal, frequency)))
        first = row["response"][f"{base:g}"]
        ratios = [row["response"][f"{p:g}"] / first for p in PRELOADS_UM]
        row["ratio_to_lowest_preload"] = ratios
        report["bands"].append(row)
        print(f"  {wavelength:.4f} m  {frequency:7.2f}   "
              + "  ".join(f"{row['response'][f'{p:g}']:8.4f}" for p in PRELOADS_UM)
              + "    " + "  ".join(f"{ratio:6.3f}" for ratio in ratios))

    report["penetration_um"] = {f"{p:g}": [value[0] * 1e6, value[1] * 1e6]
                                for p, value in penetration.items()}
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
