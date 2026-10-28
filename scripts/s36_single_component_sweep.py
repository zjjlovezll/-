"""One wavelength at a time: is the transfer nonlinear in amplitude, or is it band leakage?

`s35` measured that the mixture's band gains are not proportional to the applied depth, and that
the drift points in opposite directions in different bands.  Two mechanisms were ruled out:
the wheel never leaves the rail (0.0 % of the window) and the contact point does not migrate
(labour `s36b`: lever_y constant to 1e-6 m over +-150 um of rail height).

A third mechanism is left and it has a different consequence: with four components in the record,
a nonlinear contact turns the strong low-frequency components into combination tones that fall
inside the *other* bands' frequency bins.  Then the measured "gain at 194 Hz" contains energy that
did not come from the 0.1004 m component, and the per-band gains would drift in different
directions -- exactly what was seen -- while each individual wavelength on its own stays linear.

That is testable and the test is cheap: excite one wavelength at a time and sweep the amplitude.
If each wavelength's own gain is flat, the 50 % band hit rate is a *leakage* problem (fixable by
narrow-band excitation and per-band calibration, no new physics).  If the gain still moves with
amplitude, the nonlinearity is intrinsic to that band.

A preload sweep was tried first and abandoned: raising one rail by 85 um makes the z-only seat land
on the "standing on one side" branch (6598.8 N to 112762.4 N across eight wheels), and raising both
rails equally leaves the mean penetration unchanged because the seat re-equilibrates to the same
weight-determined 65.47 um.  So the mean preload is not a free variable here and the mechanism had
to be tested the other way round.

Usage:
    PYTHONPATH=src python -X utf8 scripts/s36_single_component_sweep.py
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
OUT_DIR = Path("../scratch/s36")
PATCH_M = (42.5, 45.5)
STEP_M = 2.5e-3
FADE_M = 0.05
WAVELENGTHS_M = (0.1004, 0.1379, 0.2073, 0.2293)   # the four s35 drew
LEVELS_MM = (0.1, 0.2, 0.3)
HALF_GAUGE_M = 0.7465
X_START_M = 30.0
LEAD_AXLE_OFFSET_M = 10.0
SPEED_KMH = 70.3206
PHASE = 0.0


def track_for(level_mm: float, wavelength_m: float) -> IrregularityTrack:
    start, end = PATCH_M
    count = int(round((end - start) / STEP_M)) + 1
    s_m = start + STEP_M * np.arange(count)
    wave = np.sin(2.0 * math.pi * s_m / wavelength_m + PHASE)
    scale = (0.5 * level_mm * 1.0e-3) / float(np.max(np.abs(wave)))
    return IrregularityTrack(s_m=s_m, lateral_m=np.zeros_like(s_m),
                             vertical_m=scale * wave,
                             roll_rad=np.zeros_like(s_m), gauge_m=np.zeros_like(s_m),
                             source=f"single {wavelength_m} m, pp {level_mm} mm")


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
    raw["id"] = f"s36_{name}"
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
    parser.add_argument("--json", type=Path, default=OUT_DIR / "single_sweep.json")
    args = parser.parse_args(argv)

    speed = SPEED_KMH / 3.6
    entry_s = (PATCH_M[0] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    exit_s = (PATCH_M[1] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    print(f"straight route, {SPEED_KMH:.2f} km/h, one wavelength at a time, "
          f"levels {LEVELS_MM} mm pp, window {entry_s:.4f}..{exit_s:.4f} s")
    if args.duration < exit_s:
        raise SystemExit("--duration ends before the axle leaves the patch")

    report = {"route": "straight", "speed_kmh": SPEED_KMH, "levels_mm": list(LEVELS_MM),
              "window_s": [entry_s, exit_s], "components": []}
    for wavelength in WAVELENGTHS_M:
        frequency = speed / wavelength
        print(f"\n  lambda {wavelength:.4f} m  f {frequency:7.2f} Hz")
        entry = {"lambda_m": wavelength, "frequency_hz": frequency, "runs": {}}
        for level in LEVELS_MM:
            name = f"case_single_{wavelength:.4f}_{level:g}mm.json"
            path = build_case(duration_s=args.duration, name=name)
            case = load_vehicle_case(path)
            result = simulate_vehicle(shift_left_rails(
                case, scaled_track(track_for(level, wavelength), channels=("vertical",),
                                   start_m=PATCH_M[0], end_m=PATCH_M[1], fade_m=FADE_M)))
            summary = result.summary
            failing = [gate for gate, ok in summary["gates"].items() if not ok]
            if summary["result_status"] != "numerically_checked":
                raise SystemExit(f"{wavelength} m at {level} mm did not integrate: {failing}")
            times = result.times_s
            mask = (times >= entry_s) & (times <= exit_s)
            window = times[mask]
            names = result.acceleration_names
            channel = next(n for n in names if n.startswith("axle1") and "z_acc" in n)
            signal = result.accelerations[mask, names.index(channel)]
            response = float(abs(complex_amplitude(window, signal, frequency)))
            penetrations = [result.contacts[i]["axle1_left"].geometry.penetration_m
                            for i in np.nonzero(mask)[0]
                            if result.contacts[i].get("axle1_left") is not None
                            and result.contacts[i]["axle1_left"].geometry is not None]
            applied = 0.5 * level * 1.0e-3          # peak amplitude of a single sine, metres
            gain = response / (applied * 1e6)       # (m/s2) per um of peak amplitude
            entry["runs"][f"{level:g}"] = {
                "status": summary["result_status"],
                "gates": int(sum(summary["gates"].values())),
                "max_penetration_um": summary["max_penetration_m"] * 1e6,
                "mean_penetration_um": float(np.mean(penetrations)) * 1e6 if penetrations else 0.0,
                "response_m_per_s2": response, "gain_per_um": gain}
            print(f"    {level:g} mm: {summary['result_status']} gates "
                  f"{sum(summary['gates'].values())}/{len(summary['gates'])} "
                  f"mean pen {np.mean(penetrations) * 1e6:7.2f} um  response {response:9.4f}"
                  f" m/s2  gain {gain:8.4f} (m/s2)/um")
        gains = [entry["runs"][f"{level:g}"]["gain_per_um"] for level in LEVELS_MM]
        spread = max(gains) / min(gains) if min(gains) > 0 else float("inf")
        entry["gain_spread"] = spread
        entry["linear"] = bool(spread <= 1.25)
        report["components"].append(entry)
        print(f"    gain spread across the sweep: {spread:.3f}x -> "
              f"{'linear' if entry['linear'] else 'AMPLITUDE DEPENDENT'}")

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    linear = sum(1 for entry in report["components"] if entry["linear"])
    print(f"\n  components whose own gain is flat within 1.25x: {linear}/"
          f"{len(report['components'])}")
    print(f"  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
