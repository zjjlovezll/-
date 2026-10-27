"""S9g: with a wheelset longitudinal coordinate, does the axle-box x channel see corrugation?

Runs the same 50 mm / 30 micron corrugation as S9-6 at 80 km/h and 20 kHz, on the vehicle whose
wheelsets carry `x`, and compares the longitudinal channel against the vertical one.
"""
from __future__ import annotations

import json
from dataclasses import replace
import pathlib
import sys
import time

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import s9f_shortwave as base  # one implementation of the corrugation and the spectrum

from velch.io.history import read_history
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

WORK = pathlib.Path(r"F:\velch_tmp\s9g")
VEHICLE = "CRH380A_M_axlebox_x"
#: The vehicle file carries 350 km/h.  Overriding it on the loaded case keeps S9-6 comparable
#: (80 km/h, 50 mm -> 444 Hz) and, more importantly, makes the reported excitation frequency come
#: from the case that actually ran instead of from a module constant that the case can contradict.
SPEED_M_S = 80.0 / 3.6
#: Which irregularity component the track carries.  "vertical" is the S9-6 corrugation;
#: "lateral" moves the contact point across the profile, which changes the rolling radius and
#: therefore the longitudinal creepage — the only route by which a long-wave geometry change can
#: reach the longitudinal channel on a straight track.
CHANNEL = "vertical"
CHANNELS = (
    "axle1_box_left_x_acc_m_per_s2",
    "axle1_box_left_z_acc_m_per_s2",
    "axle1_box_left_y_acc_m_per_s2",
)


def corrugation(tmp: pathlib.Path) -> pathlib.Path:
    """A single-wavelength corrugation in the component the run is testing.

    S9-6's generator fills only the vertical column, so asking it for a lateral case produced a
    file with a zero lateral column and a run that could not differ — a measured nothing that
    looks like a measured zero.
    """

    from velch.irregularity import IrregularityTrack, write_tre

    count = int(round(base.TRE_LENGTH_M / base.TRE_STEP_M)) + 1
    s_m = np.arange(count, dtype=float) * base.TRE_STEP_M
    wave = base.DEPTH_M * np.sin(2.0 * np.pi * s_m / base.WAVELENGTH_M)
    columns = {name: np.zeros_like(s_m) for name in ("lateral_m", "vertical_m", "roll_rad", "gauge_m")}
    columns[f"{CHANNEL}_m"] = wave
    path = tmp / f"corrugation_{CHANNEL}_{base.DEPTH_M * 1e6:.0f}um.tre"
    write_tre(path, IrregularityTrack(s_m=s_m, **columns),
              comment=f"S9-7 {CHANNEL} corrugation: {base.WAVELENGTH_M * 1e3:.0f} mm, "
                      f"{base.DEPTH_M * 1e6:.0f} um")
    return path


def build(tmp: pathlib.Path, tre: pathlib.Path) -> pathlib.Path:
    doc = json.loads(base.BASE.read_text(encoding="utf-8"))
    base.absolute(doc, base.BASE.parent)
    doc.pop("initial_state", None)
    doc.pop("topology", None)              # let vehicle_ref supply the 90-coordinate layout
    doc.pop("vehicle", None)
    doc["vehicle_ref"] = VEHICLE
    doc["case_id"] = f"s9g_{VEHICLE}"
    run = doc.setdefault("run", {})
    run.update({
        "method": "BDF", "jacobian": "analytic", "rtol": 1e-4, "atol": 1e-8,
        "x_start_m": base.X_START_M,
        "duration_s": base.DURATION_S,
        "output_step_s": base.OUTPUT_STEP_S,
        "max_solver_step_s": base.SOLVER_STEP_S,
    })
    doc["irregularity"] = {
        "tre": str(tre), "start_m": 0.0, "end_m": 1.0e6, "fade_m": 0.0,
        "scale": 1.0, "channels": [CHANNEL],
    }
    path = tmp / f"case_s9g_{CHANNEL}.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    tre = corrugation(WORK)
    case = build(WORK, tre)
    loaded = load_vehicle_case(case)
    if abs(loaded.vehicle.travel_speed_m_s - SPEED_M_S) > 1e-9:
        loaded = replace(loaded, vehicle=replace(loaded.vehicle, travel_speed_m_s=SPEED_M_S))
    print(f"vehicle {VEHICLE}: {len(loaded.initial_q)} coordinates, "
          f"{loaded.vehicle.travel_speed_m_s * 3.6:.1f} km/h")
    started = time.perf_counter()
    result = simulate_vehicle(loaded)
    elapsed = time.perf_counter() - started
    out = WORK / f"out_{CHANNEL}"
    out.mkdir(exist_ok=True)
    history_path, manifest = save_vehicle_result(loaded, result, out)
    status = json.loads(pathlib.Path(manifest).read_text(encoding="utf-8"))["summary"]["result_status"]
    print(f"  simulated in {elapsed:.1f} s -> {status}")

    history = read_history(pathlib.Path(history_path))
    names = list(history.ordering)
    time_s = np.asarray(history.data[names.index("time_s")], dtype=float)
    rate = 1.0 / float(np.mean(np.diff(time_s)))
    excitation = loaded.vehicle.travel_speed_m_s / base.WAVELENGTH_M
    print(f"  {len(time_s)} samples, {rate:.0f} Hz, excitation {excitation:.1f} Hz")

    report = {"vehicle": VEHICLE, "channel": CHANNEL, "coordinates": len(loaded.initial_q), "rate_hz": rate,
              "excitation_hz": excitation, "seconds": elapsed, "status": status, "channels": {}}
    for name in CHANNELS:
        if name not in names:
            print(f"  {name}: MISSING")
            continue
        values = np.asarray(history.data[names.index(name)], dtype=float)
        freqs, amplitude = base.spectrum(values, rate)
        centre = int(np.argmin(np.abs(freqs - excitation)))
        peak = float(amplitude[centre])
        gain = peak / base.DEPTH_M
        # the strongest line of the whole record, for context
        loudest = int(np.argmax(amplitude[1:])) + 1
        print(f"  {name}")
        print(f"    rms {np.sqrt(np.mean(values**2)):.6e}  at {excitation:.1f} Hz: {peak:.6e}"
              f"  gain {gain:.1f} (m/s^2)/m")
        print(f"    loudest line {freqs[loudest]:.1f} Hz at {amplitude[loudest]:.6e}")
        report["channels"][name] = {
            "rms": float(np.sqrt(np.mean(values**2))),
            "peak_at_excitation": peak,
            "gain_per_metre": gain,
            "loudest_hz": float(freqs[loudest]),
            "loudest_amplitude": float(amplitude[loudest]),
        }

    vertical = report["channels"].get("axle1_box_left_z_acc_m_per_s2", {}).get("gain_per_metre")
    longitudinal = report["channels"].get("axle1_box_left_x_acc_m_per_s2", {}).get("gain_per_metre")
    if vertical and longitudinal:
        report["longitudinal_over_vertical"] = longitudinal / vertical
        print(f"  longitudinal / vertical gain = {longitudinal / vertical:.4f}")
    (WORK / f"longitudinal_{CHANNEL}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("  wrote", WORK / f"longitudinal_{CHANNEL}.json")
    return 0


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        CHANNEL = sys.argv[1]
    if len(sys.argv) > 2:
        # The profile grid is 0.25 mm, so a lateral displacement below that is invisible to the
        # search.  Overriding the depth is how that limit gets measured instead of assumed.
        base.DEPTH_M = float(sys.argv[2]) * 1.0e-6
    raise SystemExit(main())
