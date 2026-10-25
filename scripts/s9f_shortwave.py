# -*- coding: utf-8 -*-
"""S9-6: can the chain carry short-wave content at all?  Raise the sampling rate and look.

The physics question is narrow and answerable in one run.  At 350 km/h a 50 mm corrugation sits at
1944 Hz, which the 2 kHz output cannot carry; at 80 km/h the same corrugation is 444 Hz, which it
can.  So this script builds a **known** corrugation (50 mm wavelength, 30 um amplitude), runs the
straight axle-box case at 80 km/h with 20 kHz output and a 10 kHz solver step cap, and reports:

* whether the axle-box spectrum peaks at the excitation frequency (444 Hz) or somewhere else;
* the measured acceleration amplitude against the two references that decide the physics:
  ``(2*pi*f)^2 * A`` (what a wheel that followed the rail would do) and the contact-stiffness
  estimate ``k_c * A / m_unsprung`` (what an inertia-limited wheel does);
* the "gain" in (m/s^2)/m, so it can be compared with the 96.5 measured at 0.1 m / 350 km/h.

The point is NOT to invert anything yet.  It is to establish that the sampling chain is honest:
if the peak lands at 444 Hz with the amplitude the contact model predicts, the pipeline can be
used for short-wave work at all; if it lands elsewhere, everything downstream is fiction.

Reference: `docs/FLEXIBLE_WHEELSET_PORT_2026-10-24.md` §20 records the result.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))  # noqa: E402
sys.path.insert(0, str(REPO / "scripts"))  # noqa: E402

WORK = Path(r"F:\velch_tmp\s9f")
BASE = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
WAVELENGTH_M = 0.050
DEPTH_M = 30.0e-6
SPEED_M_S = 80.0 / 3.6
OUTPUT_STEP_S = 5.0e-5          # 20 kHz
SOLVER_STEP_S = 1.0e-4          # 10 kHz cap: ~10 samples per 444 Hz period
DURATION_S = 0.45
X_START_M = 20.0
TRE_STEP_M = 0.0025             # 20 samples per corrugation period
TRE_LENGTH_M = 60.0


def absolute(node, base: Path) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"file", "files", "path"} and isinstance(value, str):
                node[key] = str((base / value).resolve()) if not Path(value).is_absolute() else value
            else:
                absolute(value, base)
    elif isinstance(node, list):
        for item in node:
            absolute(item, base)


def build_corrugation() -> Path:
    from velch.irregularity import IrregularityTrack, write_tre

    count = int(round(TRE_LENGTH_M / TRE_STEP_M)) + 1
    s_m = np.arange(count, dtype=float) * TRE_STEP_M
    phase = 2.0 * np.pi * s_m / WAVELENGTH_M
    vertical = DEPTH_M * np.sin(phase)
    track = IrregularityTrack(
        s_m=s_m,
        lateral_m=np.zeros_like(s_m),
        vertical_m=vertical,
        roll_rad=np.zeros_like(s_m),
        gauge_m=np.zeros_like(s_m),
    )
    path = WORK / "corrugation_50mm.tre"
    write_tre(path, track, comment="S9-6 known corrugation: 50 mm, 30 um, vertical only")
    return path


def build_case(tre: Path, flexible: bool) -> Path:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base.pop("initial_state", None)
    for body in base.get("topology", {}).get("bodies", []):
        if body.get("kind") == "axlebox" and isinstance(body.get("axle"), int):
            body["axle"] = body["axle"] - 1
    absolute(base["rail_templates"], BASE.parent)
    absolute(base["wheels"], BASE.parent)
    base["case_id"] = "s9f_corrugation_50mm"
    base["vehicle"]["travel_speed_m_s"] = SPEED_M_S
    base["run"].update({
        "x_start_m": X_START_M,
        "duration_s": DURATION_S,
        "output_step_s": OUTPUT_STEP_S,
        "max_solver_step_s": SOLVER_STEP_S,
    })
    base["irregularity"] = {
        "tre": str(tre), "start_m": 0.0, "end_m": 1.0e6, "fade_m": 0.5, "scale": 1.0,
        "channels": ["vertical"],
    }
    if flexible:
        base["flexible_wheelset"] = {
            "source": "file",
            "file": str(REPO / "vehicles" / "modes" / "CRH3C_wheelset_fe.json"),
            "axles": [1, 2, 3, 4],
        }
    target = WORK / ("case_flexible.json" if flexible else "case_rigid.json")
    target.write_text(json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def spectrum(values: np.ndarray, rate: float) -> tuple[np.ndarray, np.ndarray]:
    window = np.hanning(len(values))
    amplitude = np.abs(np.fft.rfft((values - values.mean()) * window)) * (2.0 / float(window.sum()))
    return np.fft.rfftfreq(len(values), d=1.0 / rate), amplitude


def main() -> int:
    from velch.io.history import read_history
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

    WORK.mkdir(parents=True, exist_ok=True)
    tre = build_corrugation()
    excitation_hz = SPEED_M_S / WAVELENGTH_M
    geometric = (2.0 * math.pi * excitation_hz) ** 2 * DEPTH_M
    print(f"corrugation {WAVELENGTH_M * 1e3:.0f} mm at {SPEED_M_S * 3.6:.0f} km/h -> "
          f"{excitation_hz:.1f} Hz; a following wheel would be {geometric:.0f} m/s^2 "
          f"({geometric / 9.80665:.0f} g)")
    print(f"output {1.0 / OUTPUT_STEP_S / 1e3:.0f} kHz, solver cap {SOLVER_STEP_S * 1e6:.0f} us")

    summary = {"excitation_hz": excitation_hz, "geometric_m_s2": geometric,
               "depth_m": DEPTH_M, "speed_m_s": SPEED_M_S, "runs": {}}
    for label, flexible in (("rigid", False), ("flexible", True)):
        case_path = build_case(tre, flexible)
        loaded = load_vehicle_case(case_path)
        result = simulate_vehicle(loaded)
        out = WORK / f"out_{label}"
        out.mkdir(parents=True, exist_ok=True)
        save_vehicle_result(loaded, result, out)
        history = read_history(out / "history.csv")
        time = np.asarray(history.data[history.ordering.index("time_s")], dtype=float)
        rate = 1.0 / float(np.mean(np.diff(time)))
        entry = {"frames": int(len(time)), "rate_hz": rate,
                 "coordinates": int(result.positions.shape[1]),
                 "status": result.summary.get("result_status")}
        for axis in ("z", "x"):
            column = f"axle1_box_left_{axis}_acc_m_per_s2"
            if column not in history.ordering:
                entry[axis] = None
                continue
            values = np.asarray(history.data[history.ordering.index(column)], dtype=float)
            frequencies, amplitude = spectrum(values, rate)
            inside = (frequencies > 0.5 * excitation_hz) & (frequencies < 1.5 * excitation_hz)
            index = int(np.argmax(np.where(inside, amplitude, 0.0)))
            peak_hz = float(frequencies[index])
            peak = float(amplitude[index])
            entry[axis] = {
                "rms": float(np.std(values)), "peak_hz": peak_hz, "peak_m_s2": peak,
                "gain_per_m": peak / DEPTH_M,
                "ratio_to_following": peak / geometric,
                "peak_g": peak / 9.80665,
            }
            print(f"\n{label} {axis}: rms {entry[axis]['rms']:.3f} m/s^2, "
                  f"peak {peak:.1f} m/s^2 ({entry[axis]['peak_g']:.1f} g) at {peak_hz:.1f} Hz")
            print(f"  gain {entry[axis]['gain_per_m']:.0f} (m/s^2)/m, "
                  f"{entry[axis]['ratio_to_following'] * 100:.2f} % of a following wheel")
        summary["runs"][label] = entry
    (WORK / "shortwave.json").write_text(json.dumps(summary, indent=2, default=float),
                                         encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
