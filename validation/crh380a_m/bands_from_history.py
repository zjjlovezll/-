"""Band RMS of a recorded run over a station window, for comparison with Simpack.

Reads only the run's history.csv -- no simulation. Simpack's numbers for the same
window (leading axle 78.8..82.2 m) are hard-coded from `damping_calibration.json` so the
comparison stays in one place and cannot drift.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

SIMPACK = {"rms_kN": 23.301, "dominant_Hz": 57.968,
           "30-60": 14.840, "150-250": 4.041, "250-400": 2.334}
LOW_M, HIGH_M = 78.8, 82.2
BANDS = ((30.0, 60.0), (150.0, 250.0), (250.0, 400.0))


def load(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    header = path.read_text(encoding="utf-8").splitlines()[0].split(",")
    data = np.genfromtxt(path, delimiter=",", skip_header=1)
    column = {name: index for index, name in enumerate(header)}
    return data[:, column["time_s"]], data[:, column["axle1_x_m"]], data[:, column["axle1_right_normal_n"]]


def main(paths: list[str]) -> int:
    print(f"{'run':>18}{'rms':>9}{'dom Hz':>9}{'30-60':>9}{'150-250':>10}{'250-400':>10}{'peak':>8}{'min':>8}")
    print(f"{'Simpack':>18}{SIMPACK['rms_kN']:>9.2f}{SIMPACK['dominant_Hz']:>9.2f}"
          f"{SIMPACK['30-60']:>9.2f}{SIMPACK['150-250']:>10.2f}{SIMPACK['250-400']:>10.2f}"
          f"{'      -':>8}{'      -':>8}")
    for item in paths:
        path = Path(item)
        if path.is_dir():
            path = path / "history.csv"
        time, station, force = load(path)
        keep = (station >= LOW_M) & (station <= HIGH_M)
        time, force = time[keep], force[keep] / 1e3
        step = float(np.median(np.diff(time)))
        grid = np.arange(time[0], time[-1], step)
        values = np.interp(grid, time, force)
        centred = values - values.mean()
        spectrum = np.abs(np.fft.rfft(centred)) * (2.0 / centred.size)
        freq = np.fft.rfftfreq(centred.size, step)
        bands = {f"{low:g}-{high:g}": float(np.sqrt(np.sum(spectrum[(freq >= low) & (freq < high)] ** 2) / 2.0))
                 for low, high in BANDS}
        dominant = float(freq[int(np.argmax(spectrum[1:]) + 1)])
        amp = float(np.sqrt(np.mean(centred ** 2)))
        print(f"{path.parent.name:>18}{amp:>9.2f}{dominant:>9.2f}{bands['30-60']:>9.2f}"
              f"{bands['150-250']:>10.2f}{bands['250-400']:>10.2f}"
              f"{force.max():>8.1f}{force.min():>8.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
