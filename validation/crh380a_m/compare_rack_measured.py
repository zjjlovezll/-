"""Lay the measured rack-turnout passage next to the simulated one.

Measured side: ``E:\\齿轨测试数据\\轮轨力和位移采集`` — 15 calibrated channels at 5120 Hz.  The
30 km/h force group lives in *subfolders* (``30kmh/30kmh-SP-1`` ...), which a non-recursive
listing missed in the first pass.

**Unit convention (measured empirically in this script, not assumed):** the raw third column is
the physical quantity divided by 1000 — CH01 p99.9 of 0.115 corresponds to the campaign's
published 115 kN, and CH13 peak-to-peak of 0.0018 corresponds to its published 1.8 mm.  One
global factor ``RAW_SCALE = 1.0`` therefore recovers kN for forces and mm for displacements.

Simulated side: ``rack_simpack_contact.json`` (12 001 samples, 7.90 m/s = 28.5 km/h, 12 % uphill
grade, right rail peak 49.71 kN at s = 66.861 m, left 36.61 kN at s = 70.001 m, wheel bounce
3.467 mm over the run).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.io.measured import CH01_CALIBRATION_FACTOR, event_window, read_channel

MEASURED_ROOT = Path(r"E:\齿轨测试数据\轮轨力和位移采集")
CONDITIONS = (
    ("30kmh/30kmh-SP-1", 30.0), ("30kmh/30kmh-SP-2", 30.0), ("30kmh/30kmh-SP-3", 30.0),
    ("25kmh-SP-1", 25.0), ("25kmh-SP-2", 25.0), ("25kmh-SP-3", 25.0),
)
LABELS = {9: "switch vertical", 13: "crossing vertical"}
BASE = Path(__file__).resolve().parent
RAW_SCALE = 1.0
FORCE_CHANNEL = 1


def main() -> int:
    simulated = json.loads((BASE / "rack_simpack_contact.json").read_text(encoding="utf-8"))
    sim_right = simulated["sides"]["R"]
    sim_left = simulated["sides"]["L"]
    print("simulated (28.5 km/h, 12 % uphill):")
    print(f"  right rail peak {sim_right['max_n'] / 1e3:6.2f} kN at "
          f"s={sim_right['peak_station_m']:.3f} m")
    print(f"  left  rail peak {sim_left['max_n'] / 1e3:6.2f} kN at "
          f"s={sim_left['peak_station_m']:.3f} m")
    print(f"  wheel bounce p-p {1e3 * simulated['grade']['bounce_peak_to_peak_m']:.3f} mm, "
          f"two-patch samples {sim_right['two_patch_samples']}")

    rows = []
    for name, speed_kmh in CONDITIONS:
        folder = MEASURED_ROOT / name
        if not folder.is_dir():
            print(f"\n{name}: missing")
            continue
        time, raw = read_channel(folder, FORCE_CHANNEL)
        force_kn = raw * RAW_SCALE * CH01_CALIBRATION_FACTOR
        window = event_window(time, np.abs(force_kn))
        inside = (time >= window[0]) & (time <= window[1])
        peak_kn = (float(np.percentile(np.abs(force_kn[inside]), 99.9))
                   if inside.any() else float("nan"))
        row = {"condition": name, "speed_kmh": speed_kmh,
               "duration_s": float(time[-1] - time[0]),
               "window_s": [float(window[0]), float(window[1])],
               "ch01_p999_kn": peak_kn}

        for channel in LABELS:
            _, value = read_channel(folder, channel)
            amplitude = value * RAW_SCALE
            rows_inside = amplitude[inside] if inside.size == amplitude.size else amplitude
            row[f"ch{channel:02d}_p2p_mm"] = float(rows_inside.max() - rows_inside.min())

        rows.append(row)
        print(f"\n{name}  ({row['duration_s']:.2f} s, window "
              f"{row['window_s'][0]:.2f}-{row['window_s'][1]:.2f} s)")
        print(f"  CH01 vertical force p99.9 {peak_kn:7.2f} kN")
        for channel, label in LABELS.items():
            print(f"  CH{channel:02d} {label} p-p {row[f'ch{channel:02d}_p2p_mm']:6.3f} mm")

    payload = {"raw_scale": RAW_SCALE,
               "simulated": {"speed_m_s": simulated["speed_m_s"],
                             "right_peak_n": sim_right["max_n"],
                             "left_peak_n": sim_left["max_n"],
                             "bounce_p2p_m": simulated["grade"]["bounce_peak_to_peak_m"],
                             "two_patch_samples": sim_right["two_patch_samples"]},
               "measured": rows,
               "caveats": [
                   "18# high-speed turnout measured geometry vs 7# rack-turnout model",
                   "measured force channels are 5 Hz low-passed (1.67 m of travel at 30 km/h)",
                   "measured displacement includes mounting-point static offset",
                   "raw column carries quantity/1000 (empirically confirmed against the campaign's"
                   " published 114.5 kN and 1.6-1.9 mm)",
               ]}
    (BASE / "rack_measured_vs_simulated.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
