"""S9i: short-wave depth at 350 km/h on a 20 kHz record, compared against the .tre that produced it.

S9-6 established the mechanism (a_box ~ (2 pi f_n)^2 A, so A = |a| / 24398) at 80 km/h.  This
script repeats it at line speed and, instead of reporting one gain, reconstructs the depth window
by window and compares it with the generated irregularity point by point.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import s9f_shortwave as base

from velch.irregularity import read_tre
from velch.io.history import read_history
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

WORK = pathlib.Path(r"F:\velch_tmp\s9i_high")
VEHICLE = "CRH380A_M_axlebox"   # depth only: the x layout adds a free longitudinal drift
SPEED_KMH = 350.0
DEPTH_M = 30.0e-6
WAVELENGTHS_M = (0.050,)   # the 1 944 Hz case: the one whose solver step is under test
OUTPUT_STEP_S = 5.0e-5          # 20 kHz
SOLVER_STEP_S = 2.0e-5          # 50 kHz: 26 steps per 1 944 Hz period, not 5
DURATION_S = 0.6
X_START_M = 60.0
TRE_STEP_M = 0.0025
TRE_LENGTH_M = 400.0
#: (2 pi f_n)^2 with f_n = sqrt(1.176e6/48.2)/2pi -- the single constant S9-6 measured.
PRIMARY_STIFFNESS_N_M = 1.176e6
BOX_MASS_KG = 48.2


def generator_constant() -> float:
    omega = np.sqrt(PRIMARY_STIFFNESS_N_M / BOX_MASS_KG)
    return float(omega ** 2)


def corrugation(path: pathlib.Path, wavelength_m: float) -> pathlib.Path:
    from velch.irregularity import IrregularityTrack, write_tre

    count = int(round(TRE_LENGTH_M / TRE_STEP_M)) + 1
    s_m = np.arange(count, dtype=float) * TRE_STEP_M
    wave = DEPTH_M * np.sin(2.0 * np.pi * s_m / wavelength_m)
    track = IrregularityTrack(s_m=s_m, lateral_m=np.zeros_like(s_m), vertical_m=wave,
                              roll_rad=np.zeros_like(s_m), gauge_m=np.zeros_like(s_m))
    write_tre(path, track, comment=f"S9-8 {wavelength_m * 1e3:.0f} mm, {DEPTH_M * 1e6:.0f} um")
    return path


def build(tmp: pathlib.Path, tre: pathlib.Path, label: str) -> pathlib.Path:
    doc = json.loads(base.BASE.read_text(encoding="utf-8"))
    base.absolute(doc, base.BASE.parent)
    doc.pop("initial_state", None)
    doc.pop("topology", None)
    doc.pop("vehicle", None)
    doc["vehicle_ref"] = VEHICLE
    doc["case_id"] = f"s9i_{label}"
    doc["run"].update({
        "method": "BDF", "jacobian": "analytic", "rtol": 1e-4, "atol": 1e-8,
        "x_start_m": X_START_M, "duration_s": DURATION_S,
        "output_step_s": OUTPUT_STEP_S, "max_solver_step_s": SOLVER_STEP_S,
    })
    doc["irregularity"] = {"tre": str(tre), "start_m": 0.0, "end_m": 1.0e6, "fade_m": 0.0,
                           "scale": 1.0, "channels": ["vertical"]}
    path = tmp / f"case_{label}.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def windowed(time_s: np.ndarray, values: np.ndarray, frequency: float, rate: float,
             windows: int = 10) -> list[dict]:
    """Project each slice onto the excitation frequency and read amplitude and phase."""

    result = []
    edges = np.linspace(time_s[0], time_s[-1], windows + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (time_s >= lo) & (time_s < hi)
        if mask.sum() < 20:
            continue
        t = time_s[mask]
        y = values[mask] - float(np.mean(values[mask]))
        a = 2.0 * float(np.mean(y * np.cos(2.0 * np.pi * frequency * t)))
        b = 2.0 * float(np.mean(y * np.sin(2.0 * np.pi * frequency * t)))
        result.append({"t_mid": float(t.mean()), "amplitude": float(np.hypot(a, b)),
                       "a": a, "b": b, "n": int(mask.sum())})
    return result


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    constant = generator_constant()
    print(f"(2 pi f_n)^2 = {constant:.1f} (m/s^2)/m")
    report = {"speed_kmh": SPEED_KMH, "depth_m": DEPTH_M, "constant": constant, "runs": {}}

    for wavelength in WAVELENGTHS_M:
        label = f"{wavelength * 1e3:.0f}mm"
        tre = corrugation(WORK / f"corrugation_{label}.tre", wavelength)
        case = build(WORK, tre, label)
        loaded = load_vehicle_case(case)
        speed = loaded.vehicle.travel_speed_m_s
        frequency = speed / wavelength
        print(f"\n{label}: {len(loaded.initial_q)} coordinates at {speed * 3.6:.0f} km/h, "
              f"excitation {frequency:.1f} Hz")
        started = time.perf_counter()
        result = simulate_vehicle(loaded)
        elapsed = time.perf_counter() - started
        out = WORK / f"out_{label}"
        out.mkdir(exist_ok=True)
        history_path, manifest = save_vehicle_result(loaded, result, out)
        status = json.loads(pathlib.Path(manifest).read_text(encoding="utf-8"))["summary"]["result_status"]
        history = read_history(pathlib.Path(history_path))
        names = list(history.ordering)
        time_s = np.asarray(history.data[names.index("time_s")], dtype=float)
        rate = 1.0 / float(np.mean(np.diff(time_s)))
        z = np.asarray(history.data[names.index("axle1_box_left_z_acc_m_per_s2")], dtype=float)
        print(f"  {elapsed:.1f} s, {len(time_s)} samples at {rate:.0f} Hz -> {status}")

        windows = windowed(time_s, z, frequency, rate)
        offset = float(loaded.vehicle.axle_offsets_m[0])
        track = read_tre(tre)
        recovered, truth, errors = [], [], []
        for window in windows:
            depth = window["amplitude"] / constant
            x_m = X_START_M + speed * window["t_mid"] + offset
            actual = float(np.interp(x_m, track.s_m, track.vertical_m))
            recovered.append(depth)
            truth.append(DEPTH_M)
            errors.append(depth - DEPTH_M)
            print(f"    t {window['t_mid']:6.3f} s  x {x_m:7.2f} m  "
                  f"|a| {window['amplitude']:9.3e}  recovered {depth * 1e6:6.2f} um "
                  f"(tre at x: {actual * 1e6:+7.2f} um)")
        mean = float(np.mean(recovered))
        entry = {
            "coordinates": len(loaded.initial_q), "seconds": elapsed, "status": status,
            "rate_hz": rate, "excitation_hz": frequency,
            "recovered_um": [value * 1e6 for value in recovered],
            "mean_um": mean * 1e6, "truth_um": DEPTH_M * 1e6,
            "relative_error": mean / DEPTH_M - 1.0,
            "spread_um": float(np.std(recovered)) * 1e6,
        }
        print(f"  recovered {mean * 1e6:.2f} um vs {DEPTH_M * 1e6:.2f} um truth "
              f"({100.0 * entry['relative_error']:+.1f} %), spread {entry['spread_um']:.2f} um")
        report["runs"][label] = entry

    (WORK / "highspeed.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nwrote", WORK / "highspeed.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
