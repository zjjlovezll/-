"""Is the 154 Hz ringing geometric or a contact mode?

The frog window shows a dominant 153.85 Hz where Simpack shows 57.97 Hz. Two very
different causes:

* geometric -- the excitation wavelength along the rail is fixed, so halving the speed
  must halve the observed frequency;
* a contact mode -- the wheelset ringing on the contact spring, whose frequency does
  not move with speed.

Run the same station range at half speed (duration doubled so the same kilometres are
covered) and compare the dominant frequency of the right-rail force.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_frog_N_strip05.json"
LOW_M, HIGH_M = 78.8, 82.2


def run(scale: float) -> dict:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    speed = float(raw["vehicle"]["travel_speed_m_s"])
    raw["vehicle"]["travel_speed_m_s"] = speed * scale
    raw["run"]["duration_s"] = float(raw["run"]["duration_s"]) / scale
    raw["run"]["output_step_s"] = float(raw["run"]["output_step_s"]) / scale
    raw["run"]["max_solver_step_s"] = float(raw["run"]["max_solver_step_s"]) / scale
    raw["case_id"] = f"speed_{scale:g}"
    path = BASE / f"case_speed_{scale:g}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

    case = load_vehicle_case(path)
    result = simulate_vehicle(case)
    time = np.asarray(result.times_s, dtype=float)
    force = np.array([entry["axle1_right"].normal_force_n for entry in result.contacts]) / 1e3
    station = (case.run.x_start_m + case.vehicle.axle_offsets_m[0]
               + case.vehicle.travel_speed_m_s * time)
    keep = (station >= LOW_M) & (station <= HIGH_M)
    window_time = time[keep]
    window_force = force[keep] - force[keep].mean()
    step = float(np.median(np.diff(window_time)))
    grid = np.arange(window_time[0], window_time[-1], step)
    values = np.interp(grid, window_time, window_force)
    spectrum = np.abs(np.fft.rfft(values)) * (2.0 / values.size)
    freq = np.fft.rfftfreq(values.size, step)
    index = int(np.argmax(spectrum[1:]) + 1)
    return {
        "scale": scale,
        "speed_kmh": case.vehicle.travel_speed_m_s * 3.6,
        "dominant_Hz": float(freq[index]),
        "rms_kN": float(np.sqrt(np.mean(values ** 2))),
        "peak_kN": float(force.max()),
        "lost": int(np.count_nonzero(force <= 0.0)),
        "resolution_Hz": float(freq[1]),
    }


def main() -> int:
    rows = [run(1.0), run(0.5)]
    print(f"{'speed km/h':>11}{'dominant Hz':>13}{'rms kN':>9}{'peak kN':>9}{'lost':>6}{'df Hz':>8}")
    for row in rows:
        print(f"{row['speed_kmh']:>11.1f}{row['dominant_Hz']:>13.2f}{row['rms_kN']:>9.2f}"
              f"{row['peak_kN']:>9.1f}{row['lost']:>6}{row['resolution_Hz']:>8.2f}")
    ratio = rows[0]["dominant_Hz"] / rows[1]["dominant_Hz"] if rows[1]["dominant_Hz"] else float("nan")
    print(f"  frequency ratio 350/175 = {ratio:.3f} "
          f"(geometric expects 2.0, contact mode expects 1.0)")
    (BASE / "speed_scaling.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
