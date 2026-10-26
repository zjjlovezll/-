"""Curve, inner-rail side-wear corrugation: a random mixture of 100-300 mm waves.

The defect is written into the rail profile points themselves (a dense station
table on the inner rail only), because a per-rail lateral/vertical change cannot
be expressed by a symmetric ``.tre`` record.  Geometry of the curve enters through
each station's ``y_offset_m`` (linear alignment) and ``z_offset_m`` (cant), which
is what ``velch.profiles.load_profile`` adds to the sampled section:

    y = y_section * y_sign + y_offset_m
    z = z_section * z_sign + z_offset_m

so a **common** shift of both rails keeps the gauge, and opposite ``z_offset_m``
gives the cant.

Phases of the run:
0. zero run (cant only) -> which rail is the inner one, and the noise floor;
1..3. peak-to-peak 0.1 / 0.3 / 0.5 mm, the same random mixture scaled;
then invert: calibrate the complex gain per component on the 0.1 mm run and
predict the other two.

Run:  python -X utf8 scripts/s9ag_curve_corrugation.py
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

WORK = Path(r"F:\velch_tmp\curve")
BASE_CASE = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
BASE_PRR = None  # resolved from the base case's own first station, so no CJK literal lives here
RADIUS_M = 1000.0
CANT_M = 0.0   # the static seat solves body z only, not roll: any cant lands it on one side
SPEED_KMH = 80.0
X_START_M = 20.0
# The alignment starts at the FRONT axle, not at the run start: the seat then sees
# a straight track across the whole footprint (a curved footprint at t = 0 puts the
# front axle ~50 mm away from where the wheels are and seats on the hung branch).
CURVE_START_M = X_START_M + 10.0
DURATION_S = 1.80
OUTPUT_STEP_S = 1.0e-4
SOLVER_STEP_S = 5.0e-5

PATCH_AT_M = 15.0                      # metres of curve before the patch begins
PATCH_LENGTH_M = 2.0
LAMBDA_RANGE_M = (0.100, 0.300)
COMPONENTS = 4
LEVELS_PP_M = (0.1e-3, 0.3e-3, 0.5e-3)
SEED = 20261026

STEP_INSIDE_M = 0.005                  # 20 samples per 100 mm period, 4 % interpolation loss
STEP_OUTSIDE_M = 0.25
HALF_GAUGE_M = 0.753


def speed_m_s() -> float:
    return SPEED_KMH / 3.6


def patch_start() -> float:
    return CURVE_START_M + PATCH_AT_M


def crossing_window() -> tuple[float, float]:
    """Seconds around the moment the front axle is over the middle of the patch."""
    middle = patch_start() + 0.5 * PATCH_LENGTH_M
    centre = (middle - X_START_M) / speed_m_s()
    half = 0.5 * PATCH_LENGTH_M / speed_m_s() + 0.02
    return max(0.0, centre - half), centre + half


def lateral_offset(s_m: float) -> float:
    """Linear alignment: zero up to the front axle, then s^2 / (2R) into the curve."""
    reach = max(0.0, s_m - CURVE_START_M)
    return reach * reach / (2.0 * RADIUS_M)


def mixture(seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    wavelengths = np.sort(rng.uniform(*LAMBDA_RANGE_M, size=COMPONENTS))
    phases = rng.uniform(0.0, 2.0 * math.pi, size=COMPONENTS)
    weights = rng.uniform(0.5, 1.0, size=COMPONENTS)
    return wavelengths, phases, weights / weights.sum()


def lift(s_m: float, wavelengths, phases, weights, level_pp_m: float) -> float:
    """Peak-to-peak ``level_pp_m`` mixture, zero outside the patch."""
    start = patch_start()
    end = start + PATCH_LENGTH_M
    if s_m < start or s_m > end:
        return 0.0
    total = 0.0
    for wavelength, phase, weight in zip(wavelengths, phases, weights):
        total += weight * math.cos(2.0 * math.pi * (s_m - start) / wavelength + phase)
    return 0.5 * level_pp_m * total


def normalised(wavelengths, phases, weights, level_pp_m: float) -> float:
    """Scale so the realised peak-to-peak inside the patch is exactly the level."""
    grid = np.arange(patch_start(), patch_start() + PATCH_LENGTH_M, 1.0e-4)
    values = np.array([lift(float(s), wavelengths, phases, weights, 1.0) for s in grid])
    return level_pp_m / float(values.max() - values.min())


def shifted_prr(text: str, drop: float) -> str:
    lines = text.splitlines(keepends=True)
    start = next(index for index, line in enumerate(lines) if "point.begin" in line)
    end = next(index for index, line in enumerate(lines) if "point.end" in line)
    for index in range(start + 1, end):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("!"):
            continue
        fields = stripped.split()
        if len(fields) < 2:
            continue
        try:
            y_value = float(fields[0])
            z_value = float(fields[1])
        except ValueError:
            continue
        lines[index] = f" {y_value:12.8f} {z_value - drop:12.8f}\n"
    return "".join(lines)


def station_mileages() -> list[float]:
    start, end = patch_start(), patch_start() + PATCH_LENGTH_M
    run_end = X_START_M + speed_m_s() * DURATION_S + 3.0
    inside = np.arange(start, end + STEP_INSIDE_M, STEP_INSIDE_M)
    mileages = {0.0, start, end, run_end, *[float(s) for s in inside]}
    coarse = np.arange(0.0, run_end + STEP_OUTSIDE_M, STEP_OUTSIDE_M)
    mileages.update(float(s) for s in coarse)
    return sorted(round(value, 6) for value in mileages)


def build_case(level_pp_m: float, wavelengths, phases, weights, target: Path) -> Path:
    raw = json.loads(BASE_CASE.read_text(encoding="utf-8"))
    raw.pop("initial_state", None)
    for body in raw.get("topology", {}).get("bodies", []):
        if body.get("kind") == "axlebox" and isinstance(body.get("axle"), int):
            body["axle"] = body["axle"] - 1
    raw["vehicle"]["travel_speed_m_s"] = speed_m_s()
    raw["run"]["x_start_m"] = X_START_M
    raw["run"]["duration_s"] = DURATION_S
    raw["run"]["output_step_s"] = OUTPUT_STEP_S
    raw["run"]["max_solver_step_s"] = SOLVER_STEP_S

    directory = WORK / "profiles"
    directory.mkdir(parents=True, exist_ok=True)
    # `normalised` returns the factor that turns the unit-amplitude mixture into a
    # peak-to-peak of `level_pp_m`, so the realised defect is exactly that level.
    scale = normalised(wavelengths, phases, weights, level_pp_m) if level_pp_m > 0.0 else 0.0
    templates = raw["rail_templates"]
    # The section file is taken from the case itself: hard-coding a path with CJK
    # in it survives only as long as the console encoding does (it did not).
    base_prr = Path(templates[0]["stations"][0]["profile"]["file"])
    base_text = base_prr.read_text(encoding="utf-8")
    for template_index, template in enumerate(templates):
        inner = template_index == 0          # left template first; checked against the zero run
        base_profile = dict(template["stations"][0]["profile"])
        stations = []
        for index, mileage in enumerate(station_mileages()):
            shift = lateral_offset(mileage)
            cant = CANT_M / 2.0 if template_index == 1 else -CANT_M / 2.0
            profile = dict(base_profile)
            profile["file"] = str(base_prr)
            profile["y_offset_m"] = (HALF_GAUGE_M if template_index == 1 else -HALF_GAUGE_M) + shift
            profile["z_offset_m"] = cant
            if inner and level_pp_m > 0.0:
                drop = lift(mileage, wavelengths, phases, weights, 1.0) * scale
                path = directory / f"L{index:05d}.prr"
                path.write_text(shifted_prr(base_text, drop), encoding="utf-8")
                profile["file"] = str(path)
            stations.append({"id": f"{template['id']}{index}", "s_m": mileage, "profile": profile})
        template["stations"] = stations
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    return target



def run(case: Path, label: str) -> Path:
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

    loaded = load_vehicle_case(case)
    started = time.perf_counter()
    result = simulate_vehicle(loaded)
    elapsed = time.perf_counter() - started
    out = WORK / f"out_{label}"
    out.mkdir(parents=True, exist_ok=True)
    save_vehicle_result(loaded, result, out)
    print(f"  {label}: {elapsed:.1f} s, {result.status}")
    return out


def history_rows(out: Path, names: list[str]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    from velch.io.history import read_history

    table = read_history(out / "history.csv")
    time = np.asarray(table.column("time_s"), dtype=float)
    return time, {name: np.asarray(table.column(name), dtype=float) for name in names}


def project(time: np.ndarray, values: np.ndarray, frequency: float,
            window: tuple[float, float]) -> complex:
    keep = (time >= window[0]) & (time <= window[1])
    theta = 2.0 * math.pi * frequency * time[keep]
    basis = np.column_stack((np.cos(theta), np.sin(theta), np.ones_like(theta)))
    coefficients, *_ = np.linalg.lstsq(basis, values[keep], rcond=None)
    return complex(coefficients[0], -coefficients[1])


def duty(values: dict[str, np.ndarray], window: tuple[float, float], time: np.ndarray) -> tuple:
    keep = (time >= window[0]) & (time <= window[1])
    patches = []
    for side in ("left", "right"):
        for axle in (1, 2, 3, 4):
            name = f"axle{axle}_{side}_normal_n"
            if name in values:
                patches.append(values[name][keep] > 0.0)
    if not patches:
        return 0.0, 0.0, 0.0
    active = np.array(patches)
    return (float(active.all(axis=0).mean()),
            float(values.get("axle1_left_normal_n", np.zeros_like(time))[keep].max()),
            float(values.get("axle1_right_normal_n", np.zeros_like(time))[keep].max()))


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    wavelengths, phases, weights = mixture(SEED)
    print(f"mixture: {COMPONENTS} components, wavelengths "
          + ", ".join(f"{value * 1e3:.1f} mm" for value in wavelengths))
    print("           phases " + ", ".join(f"{value:.2f}" for value in phases)
          + "  weights " + ", ".join(f"{value:.2f}" for value in weights))
    frequencies = [speed_m_s() / value for value in wavelengths]
    print("           passing frequencies at "
          + f"{SPEED_KMH:g} km/h: " + ", ".join(f"{value:.1f} Hz" for value in frequencies))
    print(f"curve R = {RADIUS_M:g} m, cant {CANT_M*1e3:g} mm, patch {patch_start():.2f}"
          f"-{patch_start()+PATCH_LENGTH_M:.2f} m, window {crossing_window()[0]:.3f}"
          f"-{crossing_window()[1]:.3f} s")

    names = ["axle1_left_normal_n", "axle1_right_normal_n", "axle1_box_left_z_acc_m_per_s2",
             "axle1_box_right_z_acc_m_per_s2"]
    for axle in (2, 3, 4):
        for side in ("left", "right"):
            names.append(f"axle{axle}_{side}_normal_n")

    summary = {"mixture": {"wavelength_m": wavelengths.tolist(), "phase_rad": phases.tolist(),
                           "weight": weights.tolist(), "frequency_hz": frequencies},
               "curve": {"radius_m": RADIUS_M, "cant_m": CANT_M, "speed_kmh": SPEED_KMH},
               "window_s": list(crossing_window()), "levels": {}}

    runs = [("zero", 0.0)] + [(f"pp{level*1e3:g}", level) for level in LEVELS_PP_M]
    measurements: dict[str, dict[str, complex]] = {}
    for label, level in runs:
        case = build_case(level, wavelengths, phases, weights, WORK / f"case_{label}.json")
        out = run(case, label)
        time, values = history_rows(out, names)
        window = crossing_window()
        done, peak_left, peak_right = duty(values, window, time)
        row = {"level_pp_m": level, "duty": done,
               "peak_left_n": peak_left, "peak_right_n": peak_right}
        for channel in ("axle1_box_left_z_acc_m_per_s2", "axle1_box_right_z_acc_m_per_s2"):
            amplitudes = [project(time, values[channel], frequency, window)
                          for frequency in frequencies]
            row[channel] = {"abs": [abs(value) for value in amplitudes],
                            "complex": [[value.real, value.imag] for value in amplitudes]}
            measurements.setdefault(label, {})[channel] = np.array(amplitudes)
        summary["levels"][label] = row
        print(f"  {label}: duty {done:.3f}, peaks {peak_left/1e3:.1f} / {peak_right/1e3:.1f} kN, "
              + " |a| " + ", ".join(f"{abs(value):.4f}" for value in
                                    measurements[label]["axle1_box_left_z_acc_m_per_s2"]))
    summary["measurements"] = {label: {channel: value.tolist() for channel, value in per.items()}
                               for label, per in measurements.items()}

    print()
    print("inversion: complex gain per component from the smallest level, then predict the rest")
    calibration = measurements["pp0.1"]["axle1_box_left_z_acc_m_per_s2"]
    truth_peak = np.array([0.5 * 0.1e-3 * weight for weight in weights])
    gains = calibration / truth_peak
    table = []
    for label in ("pp0.1", "pp0.3", "pp0.5"):
        measured = measurements[label]["axle1_box_left_z_acc_m_per_s2"]
        recovered = measured / gains
        truth = np.array([0.5 * summary["levels"][label]["level_pp_m"] * weight
                          for weight in weights])
        error = float(np.linalg.norm(recovered - truth) / np.linalg.norm(truth))
        table.append((label, summary["levels"][label]["level_pp_m"], truth, recovered, error))
        print(f"  {label}: truth p-p {summary['levels'][label]['level_pp_m']*1e6:5.0f} um  "
              + "recovered " + ", ".join(f"{abs(value)*2e6:7.1f}" for value in recovered)
              + " um  complex error " + f"{error*100:6.1f} %")
    summary["inversion"] = [{"label": label, "level_pp_m": level, "truth_peak_m": truth.tolist(),
                             "recovered_peak_m": recovered.tolist(), "complex_error": error}
                            for label, level, truth, recovered, error in table]
    (WORK / "curve_corrugation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {WORK / 'curve_corrugation.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
