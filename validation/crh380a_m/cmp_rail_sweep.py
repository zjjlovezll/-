"""Frequency-resolved comparison of every rail-support variant (frog window)."""

from __future__ import annotations

import json
import pathlib

import numpy as np

BASE = pathlib.Path(__file__).resolve().parent
CASES = [
    ("X_base (rigid)", "out_X_base"),
    ("X_support (static)", "out_X_support"),
    ("rail kz50 cz10", "out_Z_cz10"),
    ("rail kz50 cz20", "out_Z_cz20"),
    ("rail kz50 cz40", "out_Z_cz40"),
    ("rail kz50 cz80", "out_Z_cz80"),
    ("rail kz25 cz20", "out_Z_kz25_cz20"),
    ("rail kz100 cz20", "out_Z_kz100_cz20"),
]
SIMPACK = {"peak": 127.84, "min": 26.03, "lost": 0, "pen": 0.433,
           "travel": 0.594, "dominant": 39.0, "band_150_250": 1.09, "band_30_60": 4.84}


def row(label: str, directory: str) -> dict:
    root = BASE / directory
    summary = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["summary"]
    history = np.genfromtxt(root / "history.csv", delimiter=",", names=True)
    force = history["axle1_right_normal_n"]
    z = history["axle1_z_m"]
    time = history["time_s"]
    spectrum = np.fft.rfft(force - force.mean())
    freq = np.fft.rfftfreq(force.size, float(time[1] - time[0]))
    amplitude = 2.0 * np.abs(spectrum) / force.size
    band = lambda lo, hi: float(np.sqrt(np.sum(amplitude[(freq >= lo) & (freq <= hi)] ** 2))) / 1e3
    return {
        "label": label,
        "peak": float(force.max() / 1e3),
        "min": float(force.min() / 1e3),
        "mean": float(force.mean() / 1e3),
        "lost": int(np.sum(force <= 0.0)),
        "pen": summary["max_penetration_m"] * 1e3,
        "travel": float(np.ptp(z)) * 1e3,
        "dominant": float(freq[int(np.argmax(amplitude[1:])) + 1]),
        "band_150_250": band(150.0, 250.0),
        "band_30_60": band(30.0, 60.0),
    }


def main() -> int:
    rows = [row(label, directory) for label, directory in CASES]
    rows.append({**SIMPACK, "label": "Simpack", "mean": 61.3})
    header = ("label", "peak", "min", "mean", "lost", "pen", "travel", "dominant",
              "band_150_250", "band_30_60")
    print(f"{'label':>18s} {'peak':>8s} {'min':>8s} {'mean':>7s} {'lost':>5s}"
          f" {'pen':>7s} {'travel':>7s} {'domHz':>8s} {'150-250':>8s} {'30-60':>7s}")
    for row_ in rows:
        print(f"{row_['label']:>18s} {row_['peak']:8.2f} {row_['min']:8.3f} {row_['mean']:7.2f}"
              f" {row_['lost']:5d} {row_['pen']:7.3f} {row_['travel']:7.3f}"
              f" {row_['dominant']:8.2f} {row_['band_150_250']:8.3f} {row_['band_30_60']:7.3f}")
    (BASE / "sweep_rail_support.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
