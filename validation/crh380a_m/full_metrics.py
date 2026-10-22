"""Full-run metric table: mechanics + band energy, in the units the reference uses.

Bands are reported as absolute RMS (normalised share moves when the whole signal
shrinks, which made an earlier comparison misleading).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

BANDS = ((30.0, 60.0), (150.0, 250.0), (250.0, 400.0))


def read(path: Path) -> dict[str, np.ndarray]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {name: np.array([float(row[name]) for row in rows]) for name in rows[0]}


def band_rms(t: np.ndarray, f: np.ndarray, lo: float, hi: float) -> float:
    dt = float(np.median(np.diff(t)))
    signal = f - float(np.mean(f))
    amplitude = np.abs(np.fft.rfft(signal)) * 2.0 / signal.size
    freq = np.fft.rfftfreq(signal.size, dt)
    mask = (freq >= lo) & (freq < hi)
    return float(np.sqrt(np.sum(amplitude[mask] ** 2) / 2.0))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    header = f"{'run':22s} {'peak':>8s} {'min':>8s} {'lost':>5s} {'travel':>9s} {'dom':>8s}"
    for lo, hi in BANDS:
        header += f" {int(lo):3d}-{int(hi):3d}"
    print(header)
    for text in args.paths:
        path = Path(text) / "history.csv"
        columns = read(path)
        force = columns["axle1_right_normal_n"]
        travel = (columns["axle1_z_m"].max() - columns["axle1_z_m"].min()) * 1000.0
        lost = int(np.count_nonzero(force <= 1.0))
        t = columns["time_s"]
        dt = float(np.median(np.diff(t)))
        signal = force - float(np.mean(force))
        amplitude = np.abs(np.fft.rfft(signal)) * 2.0 / signal.size
        freq = np.fft.rfftfreq(signal.size, dt)
        dominant = float(freq[np.argmax(amplitude[1:]) + 1])
        row = (f"{path.parent.name:22s} {force.max() / 1e3:8.2f} {force.min() / 1e3:8.2f}"
               f" {lost:5d} {travel:9.4f} {dominant:8.2f}")
        for lo, hi in BANDS:
            row += f" {band_rms(t, force, lo, hi) / 1e3:7.3f}"
        print(row)


if __name__ == "__main__":
    main()
