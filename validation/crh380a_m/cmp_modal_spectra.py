"""Compare the contact-force spectrum of the same window across track models.

The window is a straight-run 0.05 s slice at 350 km/h, so the difference between rows is *only* the
rail track model: the frozen single-DOF compliance versus a modal beam truncated at 60 and at 320
modes.  Bands are reported up to 800 Hz because that is the range stage 2 has to cover.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

BANDS = ((30.0, 60.0), (150.0, 250.0), (250.0, 400.0), (400.0, 800.0))
HERE = Path(__file__).parent


def load(path: Path) -> tuple[np.ndarray, np.ndarray]:
    header = path.read_text(encoding="utf-8").splitlines()[0].split(",")
    data = np.genfromtxt(path, delimiter=",", skip_header=1)
    column = {name: index for index, name in enumerate(header)}
    return data[:, column["time_s"]], data[:, column["axle1_right_normal_n"]]


def statistics(run: Path) -> dict[str, float]:
    time, force = load(run / "history.csv")
    force = force / 1e3
    step = float(np.median(np.diff(time)))
    grid = np.arange(time[0], time[-1], step)
    values = np.interp(grid, time, force)
    centred = values - values.mean()
    spectrum = np.abs(np.fft.rfft(centred)) * (2.0 / centred.size)
    freq = np.fft.rfftfreq(centred.size, step)
    row = {"rms": float(np.sqrt(np.mean(centred ** 2))),
           "dominant": float(freq[int(spectrum.argmax())]),
           "peak": float(force.max()),
           "min": float(force.min()),
           "lost": int(np.sum(force <= 1e-9))}
    for low, high in BANDS:
        selected = (freq >= low) & (freq < high)
        row[f"{low:g}-{high:g}"] = float(np.sqrt(np.sum(spectrum[selected] ** 2) / 2.0))
    return row


def main(runs: list[str]) -> int:
    columns = ["rms", "dominant", "30-60", "150-250", "250-400", "400-800", "peak", "min", "lost"]
    print(f"{'run':>22}" + "".join(f"{name:>10}" for name in columns))
    for name in runs:
        row = statistics(HERE / name)
        print(f"{name:>22}" + "".join(f"{row[key]:10.3f}" for key in columns))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
