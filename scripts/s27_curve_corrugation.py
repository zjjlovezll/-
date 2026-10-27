"""Curved turnout, known corrugation: does the 18 turnout let us read the defect back?

This is gate 6 for the *curved* case.  The geometry is the real one -- ``case_diverging_R1100.json``,
R = 1100 m, 80 km/h lateral limit, the curve written in the station table -- and it is run the way
the user described: seat on the straight stock-rail section at 45 m, then start the run at 69 m and
travel through the diverging route.

The defect is a random mixture of 100..300 mm waves (the inner-rail side-wear band), written as a
``.tre`` record on the **inner** rail only.  Which rail is inner is not assumed: the curve's centre
lies on the side the design line moves towards, and ``_gauge_centre`` reports that sign, so the
script picks the rail whose centre is on that side and prints the decision.

Observables.  This case is the 35-coordinate inline vehicle, so it has **no axle box**: the channels
are the wheelset vertical acceleration and the wheel-rail normal force.  A wheelset sits below the
primary spring and therefore sees more of a 100..300 mm wave than an axle box would, so detection is
favoured and the *depth* is the number that has to be watched.

Protocol (the one the repository already uses for the ±A band work):
  1. a zero run, for the noise floor at each component frequency;
  2. peak-to-peak 0.1 / 0.3 / 0.5 mm on the same random mixture;
  3. calibrate one complex gain per component on the 0.1 mm run, then predict the other two.

Run:  python -X utf8 scripts/s27_curve_corrugation.py [--duration 0.16] [--levels 0 0.1 0.3]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from velch import data_root
from velch.irregularity import (
    IrregularityTrack,
    ShiftedSeries,
    scaled_track,
    write_tre,
)
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

SPEED_KMH = 80.0
SEAT_AT_M = 45.0          # straight stock-rail section, every axle inside the station table
RUN_AT_M = 69.0           # past the 50.578 m tangent, on the diverging route
PATCH_M = (79.6, 83.6)
STEP_M = 0.0025           # 40 samples per 100 mm period
LAMBDAS_M = (0.10, 0.30)
COMPONENTS = 4
SEED = 20261028
WINDOW_S = (0.030, 0.130)


def build_case(raw: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return load_vehicle_case(path)


def base_raw(duration_s: float) -> dict:
    raw = json.loads((data_root.case_dir() / "case_diverging_R1100.json").read_text(encoding="utf-8"))
    raw["run"].update({
        "x_start_m": RUN_AT_M,
        "seat_x_start_m": SEAT_AT_M,
        "duration_s": duration_s,
        "output_step_s": 2.0e-4,
        "max_solver_step_s": 2.0e-4,
        "rtol": 1e-6,
        "atol": 1e-8,
        "method": "BDF",
        # BDF without an analytic Jacobian is a sparse finite-difference fill on every step; the
        # analytic path is the one the fast preset uses and it cuts the wall clock by an order.
        "jacobian": "analytic",
    })
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw.pop("initial_state", None)
    raw.pop("irregularity", None)
    return raw


def mixture(peak_to_peak_m: float):
    """Random component wavelengths, phases and weights; normalised to the requested pp."""

    rng = np.random.default_rng(SEED)
    # Stratified in log-wavelength: an unstratified draw put three of four components at ~100 mm
    # and left the 200-300 mm band empty, so the mixture answered only one question.
    edges = np.linspace(math.log(LAMBDAS_M[0]), math.log(LAMBDAS_M[1]), COMPONENTS + 1)
    lambdas = np.exp([rng.uniform(edges[i], edges[i + 1]) for i in range(COMPONENTS)])
    phases = rng.uniform(0.0, 2.0 * math.pi, COMPONENTS)
    weights = rng.uniform(0.4, 1.0, COMPONENTS)
    return lambdas, phases, weights


def track_for(peak_to_peak_m: float, lambdas, phases, weights) -> IrregularityTrack:
    s = np.arange(PATCH_M[0], PATCH_M[1] + 0.5 * STEP_M, STEP_M)
    vertical = np.zeros_like(s)
    for lam, phase, weight in zip(lambdas, phases, weights):
        vertical += weight * np.sin(2.0 * math.pi * s / lam + phase)
    span = float(vertical.max() - vertical.min())
    vertical *= (peak_to_peak_m / span) if span > 0 else 0.0
    zeros = np.zeros_like(s)
    return IrregularityTrack(s_m=s, lateral_m=zeros, vertical_m=vertical,
                             roll_rad=zeros, gauge_m=zeros, source="s27 random corrugation")


def component_amplitudes(vertical: np.ndarray, s: np.ndarray, lambdas) -> np.ndarray:
    """Least-squares amplitude of each component in the generated profile itself."""

    columns = []
    for lam in lambdas:
        columns.append(np.cos(2.0 * math.pi * s / lam))
        columns.append(np.sin(2.0 * math.pi * s / lam))
    result = []
    for index in range(len(lambdas)):
        design = np.column_stack([columns[2 * index], columns[2 * index + 1]])
        coeffs, *_ = np.linalg.lstsq(design, vertical, rcond=None)
        result.append(float(math.hypot(*coeffs)))
    return np.asarray(result)


def inner_side(dynamics) -> str:
    """Which side is the inner rail, from the sign of the design line's lateral offset."""

    topology = dynamics.topology
    q = np.zeros(dynamics.dimension)
    v = np.zeros(dynamics.dimension)
    right = [rail for rail in dynamics.case.rails if str(rail.id).endswith("right")]
    left = [rail for rail in dynamics.case.rails if str(rail.id).endswith("left")]
    middle = 0.5 * (PATCH_M[0] + PATCH_M[1])

    def centre(rails) -> float:
        values = []
        for rail in rails:
            index = dynamics.case.rails.index(rail)
            lateral = dynamics.track.local_state(q, v, index, middle, SPEED_KMH / 3.6)[0]
            values.append(float(lateral))
        return float(np.mean(values))

    offset_right = centre(right)
    offset_left = centre(left)
    # The curve's centre lies on the side the design line moves towards (dy/ds grows with s), so
    # the inner rail is the one nearer that side: the larger lateral offset.
    return "right" if offset_right > offset_left else "left"


def with_defect_on(case, track, side: str):
    """Apply the record to one side only, using the loader's own wrapper.

    The record covers the patch and nothing else, and ``ShiftedSeries`` *clamps* a mileage outside
    its span instead of returning zero, so the record is windowed with a half-cosine fade whose ends
    are zero: outside the patch the clamp then adds exactly zero.
    """

    windowed = scaled_track(track, channels=("vertical",),
                            start_m=PATCH_M[0], end_m=PATCH_M[1], fade_m=0.05)
    rails = []
    for rail in case.rails:
        this_side = "left" if str(rail.id).endswith("left") else "right"
        if this_side != side:
            rails.append(rail)
            continue
        bodies = tuple(replace(body, series=ShiftedSeries(body.series, windowed, side, 0.7465))
                       for body in rail.bodies)
        rails.append(replace(rail, bodies=bodies))
    return replace(case, rails=tuple(rails))


def project(times: np.ndarray, values: np.ndarray, frequencies) -> np.ndarray:
    """Amplitude of each frequency in ``values`` over the analysis window, one linear fit."""

    columns = [np.ones_like(times), times - times.mean()]
    for frequency in frequencies:
        columns.append(np.cos(2.0 * math.pi * frequency * times))
        columns.append(np.sin(2.0 * math.pi * frequency * times))
    design = np.column_stack(columns)
    coeffs, *_ = np.linalg.lstsq(design, values, rcond=None)
    return np.asarray([float(math.hypot(coeffs[2 + 2 * i], coeffs[3 + 2 * i]))
                       for i in range(len(frequencies))])


def run_level(raw: dict, path: Path, peak_to_peak_m: float, lambdas, phases, weights, side: str):
    if peak_to_peak_m <= 0.0:
        return build_case(raw, path), None
    track = track_for(peak_to_peak_m, lambdas, phases, weights)
    tre = path.with_name(f"corrugation_{peak_to_peak_m * 1e3:g}mm.tre")
    write_tre(tre, track, comment=f"s27 {peak_to_peak_m * 1e3:g} mm pp, inner rail {side}")
    case = build_case(raw, path)
    return with_defect_on(case, track, side), tre


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=0.16)
    parser.add_argument("--levels", type=float, nargs="+", default=[0.0, 0.1, 0.3, 0.5])
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    out = Path(args.out) if args.out else (
        Path(__file__).resolve().parents[2] / "scratch" / "s27_curve")
    out.mkdir(parents=True, exist_ok=True)

    raw = base_raw(args.duration)
    lambdas, phases, weights = mixture(1.0)
    print("wavelengths (m) : " + ", ".join(f"{v:.4f}" for v in lambdas))
    print("phases (rad)    : " + ", ".join(f"{v:.4f}" for v in phases))
    print("weights         : " + ", ".join(f"{v:.4f}" for v in weights))

    reference = build_case(raw, out / "case_plain.json")
    from velch.vehicle_solver import VehicleDynamics

    side = inner_side(VehicleDynamics(reference))
    print(f"inner rail      : {side}")

    frequencies = [SPEED_KMH / 3.6 / float(lam) for lam in lambdas]
    print("frequencies (Hz): " + ", ".join(f"{v:.2f}" for v in frequencies))
    true_amp = {level: component_amplitudes(track_for(level / 1e3, lambdas, phases, weights)
                                            .vertical_m,
                                            np.arange(PATCH_M[0], PATCH_M[1] + 0.5 * STEP_M, STEP_M),
                                            lambdas)
                for level in args.levels if level > 0.0}

    results = {}
    for level in args.levels:
        case, tre = run_level(raw, out / f"case_{level:g}mm.json", level / 1e3,
                              lambdas, phases, weights, side)
        started = time.time()
        result = simulate_vehicle(case)
        elapsed = time.time() - started
        status = result.summary.get("result_status", "?")
        print(f"\n--- {level:g} mm pp : {status} in {elapsed:.1f} s ---")
        if status != "numerically_checked":
            print(json.dumps({k: v for k, v in result.summary.items()
                              if k in ("failed_gate", "message", "gates")}, indent=1,
                             default=str)[:600])
            results[level] = {"status": status, "elapsed_s": elapsed}
            continue

        times = np.asarray(result.times_s, dtype=float)
        names = list(result.acceleration_names)
        pick = [i for i, name in enumerate(names) if name.startswith("axle1") and name.endswith("_z_acc_m_per_s2")]
        if not pick:
            print("available channel names:", names[:12])
            return 2
        acceleration = np.asarray(result.accelerations, dtype=float)[:, pick[0]]
        mask = (times >= WINDOW_S[0]) & (times <= WINDOW_S[1])
        inner_force = np.asarray([frame[f"axle1_{side}"].normal_force_n
                                  for frame, keep in zip(result.contacts, mask) if keep], dtype=float)
        accel_amp = project(times[mask], acceleration[mask], frequencies)
        force_amp = project(times[mask], inner_force, frequencies)
        results[level] = {
            "status": status,
            "elapsed_s": elapsed,
            "channel": names[pick[0]],
            "acceleration_amplitude": accel_amp.tolist(),
            "inner_force_amplitude": force_amp.tolist(),
            "force_mean_n": float(np.mean(inner_force)),
        }
        print(f"channel {names[pick[0]]}")
        for index, lam in enumerate(lambdas):
            print(f"  lambda {lam * 1e3:6.1f} mm  f {frequencies[index]:7.2f} Hz  "
                  f"|a| {accel_amp[index]:10.4f} m/s^2   |N| {force_amp[index]:10.1f} N")

    summary = {
        "speed_kmh": SPEED_KMH,
        "duration_s": args.duration,
        "window_s": list(WINDOW_S),
        "patch_m": list(PATCH_M),
        "inner_rail": side,
        "lambdas_m": lambdas.tolist(),
        "phases_rad": phases.tolist(),
        "weights": weights.tolist(),
        "frequencies_hz": frequencies,
        "true_component_amplitude_m": {str(k): v.tolist() for k, v in true_amp.items()},
        "levels": {str(k): v for k, v in results.items()},
    }

    # Inversion: one complex-free gain per component from the smallest excited level, predict the rest.
    excited = [level for level in args.levels if level > 0.0 and level in results
               and results[level].get("acceleration_amplitude")]
    if len(excited) >= 2:
        calibration = min(excited)
        gain = (np.asarray(results[calibration]["acceleration_amplitude"])
                / true_amp[calibration])
        gain_force = (np.asarray(results[calibration]["inner_force_amplitude"])
                      / true_amp[calibration])
        table = {}
        for level in excited:
            recovered = np.asarray(results[level]["acceleration_amplitude"]) / gain
            recovered_force = np.asarray(results[level]["inner_force_amplitude"]) / gain_force
            table[str(level)] = {
                "true_m": true_amp[level].tolist(),
                "recovered_accel_m": recovered.tolist(),
                "recovered_force_m": recovered_force.tolist(),
                "error_accel_percent": (100.0 * (recovered - true_amp[level])
                                        / true_amp[level]).tolist(),
                "error_force_percent": (100.0 * (recovered_force - true_amp[level])
                                        / true_amp[level]).tolist(),
            }
        summary["gain_m_per_s2_per_m"] = gain.tolist()
        summary["gain_n_per_m"] = gain_force.tolist()
        summary["calibrated_on_mm"] = calibration
        summary["inversion"] = table

        print("\ncalibration gains (|a| / amplitude):")
        for index, lam in enumerate(lambdas):
            print(f"  lambda {lam * 1e3:6.1f} mm  gain {gain[index]:12.4f} (m/s^2)/m   "
                  f"force gain {gain_force[index]:12.1f} N/m")
        print("\ninversion (calibrated on the smallest excited level):")
        for level in excited:
            row = table[str(level)]
            print(f"  {level:g} mm pp")
            for index, lam in enumerate(lambdas):
                print(f"    lambda {lam * 1e3:6.1f} mm  true {true_amp[level][index] * 1e6:7.2f} um  "
                      f"accel {row['recovered_accel_m'][index] * 1e6:8.2f} um "
                      f"({row['error_accel_percent'][index]:+7.1f} %)   "
                      f"force {row['recovered_force_m'][index] * 1e6:8.2f} um "
                      f"({row['error_force_percent'][index]:+7.1f} %)")

    (out / "inversion.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    print(f"\nwritten: {out / 'inversion.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
