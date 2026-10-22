"""Compare two 0.05 s frog-window runs: peak force, contact loss, spectrum, and the
sleeper-passing band (162 Hz) that the discrete support model is supposed to add."""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

BASE = pathlib.Path(__file__).resolve().parent


def load(directory: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    path = BASE / directory
    history = np.genfromtxt(path / "history.csv", delimiter=",", names=True)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    time = history["time_s"]
    force = history["axle1_right_normal_n"]
    z = history["axle1_z_m"] - np.mean(history["axle1_z_m"])
    return time, force, z, manifest


def band_rms(freq: np.ndarray, amplitude: np.ndarray, low: float, high: float) -> float:
    mask = (freq >= low) & (freq <= high)
    return float(np.sqrt(np.sum(amplitude[mask] ** 2)))


def summarise(name: str, time: np.ndarray, force: np.ndarray, z: np.ndarray, manifest: dict) -> dict:
    span = float(time[-1] - time[0])
    grid = np.linspace(time[0], time[-1], 1024)
    signal = np.interp(grid, time, force)
    spectrum = np.fft.rfft(signal - signal.mean())
    freq = np.fft.rfftfreq(grid.size, grid[1] - grid[0])
    amplitude = 2.0 * np.abs(spectrum) / grid.size
    peak_hz = float(freq[int(np.argmax(amplitude[1:])) + 1])
    summary = manifest["summary"]
    row = {
        "case": name,
        "status": summary.get("result_status"),
        "peak_kn": float(np.max(force) / 1e3),
        "min_kn": float(np.min(force) / 1e3),
        "mean_kn": float(np.mean(force) / 1e3),
        "lost": int(np.sum(force <= 0.0)),
        "max_pen_mm": summary.get("max_penetration_m", float("nan")) * 1e3,
        "wheel_z_pp_mm": float(np.ptp(z)) * 1e3,
        "dominant_hz": peak_hz,
        "rms_150_250": band_rms(freq, amplitude, 150.0, 250.0) / 1e3,
        "rms_30_60": band_rms(freq, amplitude, 30.0, 60.0) / 1e3,
        "samples": int(time.size),
        "span_s": span,
    }
    return row


def main() -> int:
    rows = []
    for name in ("out_X_base", "out_X_support", "out_Z_local_rail"):
        time, force, z, manifest = load(name)
        rows.append(summarise(name, time, force, z, manifest))
    header = ("case", "status", "peak_kn", "min_kn", "mean_kn", "lost", "max_pen_mm",
              "wheel_z_pp_mm", "dominant_hz", "rms_150_250", "rms_30_60")
    print("  ".join(f"{h:>14s}" for h in header))
    for row in rows:
        cells = []
        for key in header:
            value = row[key]
            if isinstance(value, float):
                cells.append(f"{value:14.4f}")
            else:
                cells.append(f"{str(value):>14s}")
        print("  ".join(cells))
    out = BASE / "support_compliance_ab.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("written", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
