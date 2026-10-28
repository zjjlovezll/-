"""Gate 6, straight side: corrugation at a *randomly drawn* speed, inverted one run later.

Why the straight route and not the turnout's diverging one: the curved route is blocked by a
measured contact-law boundary (see docs/CURVE_YAW_BALANCE_2026-10-28.md -- the 21 842 N curving
demand is reachable only with one side unloaded and 0.14 mm pressed into the rail head).  The
straight route runs seven gates out of seven, so the corrugation chain can be exercised there
without touching any physics.

Why the speed is drawn from 70..90 km/h and not from the train's 350 km/h: the short-wave
operator (Velch/docs/INVERSION_PIPELINE_2026-10-27.md) is calibrated per speed, and gate 5
forbids extrapolating between speeds.  70.8 km/h is the reference the operator was built on and
the measured record lives at 40..75 km/h, so 70..90 is the only band where a drawn speed may be
used at all.  Saying so here is the point: a random speed outside the table would be an
extrapolation dressed up as realism.

The protocol is the one `s31b_curve_corrugation.py` pre-registered, unchanged, so the numbers are
comparable with the curved attempt:

* four log-stratified wavelengths in 0.10..0.30 m, uniform phases, weights drawn from 0.5..0.9,
  the mixture normalised to the requested peak-to-peak;
* levels 0.0 / 0.1 / 0.3 mm peak-to-peak;
* the gain is calibrated on the smallest excited level and used to predict the largest, so the
  prediction is out of sample in amplitude;
* gates: EXCITATION_GATE (excited response at least this many times the zero-level response) and
  DEPTH_GATE_DB (recovered depth within this many dB of the applied one).

Usage:
    PYTHONPATH=src python -X utf8 scripts/s35_straight_random_speed.py --duration 0.30
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np

from velch.irregularity import IrregularityTrack, ShiftedSeries, scaled_track
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

BASE_CASE = Path("F:/velch_data/validation/crh380a_m/case_A_final_law.json")
OUT_DIR = Path("../scratch/s35")
PATCH_M = (42.5, 45.5)
STEP_M = 2.5e-3
FADE_M = 0.05
LAMBDAS_M = (0.10, 0.30)
COMPONENTS = 4
SEED = 20261028
HALF_GAUGE_M = 0.7465
X_START_M = 30.0
LEAD_AXLE_OFFSET_M = 10.0
SPEED_BAND_KMH = (70.0, 90.0)
EXCITATION_GATE = 6.0
DEPTH_GATE_DB = 2.0


def draw_speed_kmh() -> float:
    """One draw, uniform in the calibrated band.  Printed so the run is reproducible by hand."""
    rng = np.random.default_rng(SEED)
    low, high = SPEED_BAND_KMH
    return float(rng.uniform(low, high))


def draw_components() -> list[tuple[float, float, float]]:
    """Stratified wavelengths, uniform phases, weights from 0.5..0.9 -- the s31b layout."""
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
    scale = (0.5 * level_mm * 1.0e-3) / float(np.max(np.abs(total)))
    profile = scale * total
    amplitudes = {wavelength: scale * weight for wavelength, _, weight in components}
    track = IrregularityTrack(s_m=s_m, lateral_m=np.zeros_like(s_m), vertical_m=profile,
                             roll_rad=np.zeros_like(s_m), gauge_m=np.zeros_like(s_m),
                             source=f"straight corrugation, pp {level_mm} mm")
    return track, amplitudes


def build_case(*, speed_kmh: float, duration_s: float, name: str) -> Path:
    """A copy of the straight baseline case with the drawn speed and the asked-for record."""
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
    raw["vehicle"]["travel_speed_m_s"] = speed_kmh / 3.6
    raw["id"] = f"s35_{name}"
    raw["purpose"] = "synthetic"
    target = OUT_DIR / name
    target.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return target


def shift_one_rail(case, track: IrregularityTrack):
    """Wrap only the left rails' series; the right rail stays bit-exact."""
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


def run_level(*, speed_kmh: float, duration_s: float, level_mm: float, components, name: str):
    path = build_case(speed_kmh=speed_kmh, duration_s=duration_s, name=name)
    case = load_vehicle_case(path)
    track, amplitudes = mixture(level_mm, components)
    if track is not None:
        windowed = scaled_track(track, channels=("vertical",),
                                start_m=PATCH_M[0], end_m=PATCH_M[1], fade_m=FADE_M)
        case = shift_one_rail(case, windowed)
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
    parser.add_argument("--duration", type=float, default=0.30)
    parser.add_argument("--levels", type=float, nargs="+", default=[0.0, 0.1, 0.3])
    parser.add_argument("--json", type=Path, default=OUT_DIR / "inversion.json")
    args = parser.parse_args(argv)

    speed_kmh = draw_speed_kmh()
    speed = speed_kmh / 3.6
    components = draw_components()
    print(f"straight route, speed drawn from {SPEED_BAND_KMH[0]}..{SPEED_BAND_KMH[1]} km/h "
          f"with seed {SEED} -> {speed_kmh:.2f} km/h ({speed:.3f} m/s)")
    print(f"patch {PATCH_M[0]}..{PATCH_M[1]} m on the left rail, step {STEP_M * 1e3:.2f} mm")
    for wavelength, phase, weight in components:
        print(f"  lambda {wavelength:.4f} m  phase {phase:.4f}  weight {weight:.4f}  "
              f"f {speed / wavelength:7.2f} Hz")

    entry_s = (PATCH_M[0] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    exit_s = (PATCH_M[1] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    print(f"  leading axle over the patch t {entry_s * 1e3:.1f} .. {exit_s * 1e3:.1f} ms "
          f"({(exit_s - entry_s) * speed / min(w for w, _, _ in components):.1f} periods of the "
          "slowest component)")
    if args.duration < exit_s:
        raise SystemExit(f"--duration {args.duration} ends before the axle leaves the patch at "
                         f"{exit_s:.4f} s; the projection window would be truncated")

    runs = {}
    for level in args.levels:
        case, result, amplitudes = run_level(speed_kmh=speed_kmh, duration_s=args.duration,
                                            level_mm=level, components=components,
                                            name=f"case_straight_corrug_{level:g}mm.json")
        summary = result.summary
        failing = [gate for gate, ok in summary["gates"].items() if not ok]
        passed = sum(1 for ok in summary["gates"].values() if ok)
        print(f"  level {level:g} mm: {summary['result_status']} gates {passed}"
              f"/{len(summary['gates'])} failing {failing} "
              f"max pen {summary['max_penetration_m'] * 1e6:.2f} um")
        if summary["result_status"] != "numerically_checked":
            raise SystemExit(f"level {level:g} mm did not integrate; no depth may be quoted")
        runs[level] = (case, result, amplitudes)

    names = runs[args.levels[0]][1].acceleration_names
    channel = next((name for name in names if name.startswith("axle1") and "z_acc" in name), None)
    if channel is None:
        print("  acceleration channels:", ", ".join(names))
        raise SystemExit("no leading-wheelset vertical acceleration channel")
    index = names.index(channel)
    print(f"  observable {channel}")

    times = runs[args.levels[0]][1].times_s
    mask = (times >= entry_s) & (times <= exit_s)
    window = times[mask]
    print(f"  window {mask.sum()} samples")

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
        print(f"  lambda {wavelength:.4f} m  f {frequency:7.2f} Hz  applied "
              f"{[round(row['applied_um'][f'{l:g}'], 3) for l in args.levels]} um  "
              f"response {[round(row['response'][f'{l:g}'], 6) for l in args.levels]} m/s2")

    excited = [level for level in args.levels if level > 0.0]
    if len(excited) < 2:
        raise SystemExit("need two excited levels: one to calibrate a gain, one to test it")
    calibration, targets = excited[0], excited[1:]

    # Why a depth can only be quoted where the wheel stays on the rail: the static penetration is
    # 65.47 um, so a record whose peak-to-peak is larger than twice that lifts the wheel clear of
    # the rail once per cycle.  Counting the frames in the window with no active contact on the
    # observed wheel is the measurement that separates "the operator is wrong" from "the wheel was
    # in the air".  It is reported per level, not folded into the depth.
    loss = {}
    for level in args.levels:
        rail_id = f"axle1_{'left' if 'left' in channel else 'right'}"
        airborne = 0
        for index_t in np.nonzero(mask)[0]:
            response = runs[level][1].contacts[index_t].get(rail_id)
            if response is None or not response.active or response.geometry is None:
                airborne += 1
        loss[f"{level:g}"] = airborne / max(int(mask.sum()), 1)
    print("  fraction of the window with this wheel off the rail: "
          + ", ".join(f"{float(level):g} mm {value * 100:.1f} %"
                      for level, value in loss.items()))

    quiet_gate = {}
    quiet = [level for level in args.levels if level == 0.0]
    if quiet:
        zero = quiet[0]
        for row in rows:
            quiet_gate[f"{row['lambda_m']:.4f}"] = (
                row["response"][f"{calibration:g}"] / max(row["response"][f"{zero:g}"], 1e-15))

    hits = []
    report = {"route": "straight", "speed_kmh": round(speed_kmh, 4),
              "speed_seed": SEED, "speed_band_kmh": list(SPEED_BAND_KMH),
              "patch_m": list(PATCH_M), "window_s": [entry_s, exit_s],
              "levels_mm": list(args.levels), "channel": channel,
              "calibration_level_mm": calibration, "target_levels_mm": targets,
              "excitation_gate": EXCITATION_GATE, "depth_gate_db": DEPTH_GATE_DB,
              "contact_loss_fraction": loss, "components": [], "quiet_gate": quiet_gate}
    print(f"  gain calibrated on {calibration:g} mm, applied to {targets} mm (out of sample)")
    for row in rows:
        gain = row["response"][f"{calibration:g}"] / row["applied_um"][f"{calibration:g}"]
        row["gain_m_per_s2_per_um"] = gain
        row["predictions"] = {}
        row_hits = []
        for target in targets:
            recovered = row["response"][f"{target:g}"] / gain
            applied = row["applied_um"][f"{target:g}"]
            ratio = recovered / applied
            db = 20.0 * math.log10(ratio)
            ok = abs(db) <= DEPTH_GATE_DB
            row_hits.append(bool(ok))
            row["predictions"][f"{target:g}"] = {"recovered_um": recovered,
                                                 "applied_um": applied,
                                                 "error_db": db, "within_gate": bool(ok)}
            print(f"  lambda {row['lambda_m']:.4f} m @ {target:g} mm: applied {applied:7.3f} um "
                  f"-> recovered {recovered:7.3f} um  ({db:+6.2f} dB)  "
                  f"{'PASS' if ok else 'FAIL'}")
        hits.extend(row_hits)
        report["components"].append(row)

    report["band_hits"] = int(sum(hits))
    report["band_total"] = int(len(hits))
    report["verdict"] = "pass" if all(hits) else "degraded"
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n  bands within +-{DEPTH_GATE_DB:g} dB: {sum(hits)}/{len(hits)}"
          f"  -> verdict: {report['verdict'].upper()}")
    print(f"  wrote {args.json}")
    return 0 if all(hits) else 1


if __name__ == "__main__":
    raise SystemExit(main())
