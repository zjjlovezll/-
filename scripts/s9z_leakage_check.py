"""Is the 40 m band's phase sensitivity spectral leakage?

The three-phase replay of the long-wave target (`scripts/s9y_longwave_phases.py`)
gave calibration 1.9 / 0.4 / 12.4 % for phases 1.0065 / 3.1009 / 5.1953 rad, and the
whole spread sits in the 40 m band (-0.6 % vs -15.9 %).  A 2 s record at 97.22 m/s
covers 194.4 m = 4.86 cycles of 40 m, i.e. NOT an integer number of cycles, so the
projection of a finite record onto that single frequency depends on where in the
cycle the window starts.

This script measures that directly: for each phase's differential record it fits
one complex amplitude at the band's frequency inside the analysis window and
reports the residual fraction.  Leakage predicts residual/amplitude growing with
the phase offset; a physical effect would not care about the window's phase.

Run:  python -X utf8 scripts/s9z_leakage_check.py
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from velch.io.history import read_history  # noqa: E402

WORK = pathlib.Path(r"F:\velch_tmp\s9i")
SPEED = 97.2222
BANDS = (20.0, 40.0)
CHANNEL = "axle1_box_left_z_acc_m_per_s2"


def load(folder: pathlib.Path) -> tuple[np.ndarray, np.ndarray]:
    history = read_history(folder / "history.csv")
    time = np.asarray(history.data[history.ordering.index("time_s")], dtype=float)
    name = CHANNEL if CHANNEL in history.ordering else "axle1_z_acc_m_per_s2"
    values = np.asarray(history.data[history.ordering.index(name)], dtype=float)
    return time, values


def main() -> int:
    rows = []
    print(f"{'phase':>10} {'band':>6} {'amplitude':>11} {'residual':>10} {'res/amp':>9} {'cycles':>7}")
    for index in range(3):
        plus = WORK / f"out_phase{index}_plus"
        minus = WORK / f"out_phase{index}_minus"
        if not (plus.is_dir() and minus.is_dir()):
            continue
        time, first = load(plus)
        _, second = load(minus)
        differential = 0.5 * (first - second)
        start = 0.15 * time[-1]
        stop = 0.95 * time[-1]
        window = (time >= start) & (time <= stop)
        t = time[window]
        y = differential[window]
        for band in BANDS:
            frequency = SPEED / band
            design = np.column_stack([np.cos(2.0 * np.pi * frequency * t), np.sin(2.0 * np.pi * frequency * t)])
            coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
            fit = design @ coefficients
            amplitude = float(np.hypot(*coefficients))
            residual = float(np.std(y - fit))
            cycles = (stop - start) * frequency
            print(f"{index:>10} {band:6.0f} {amplitude:11.5f} {residual:10.5f} "
                  f"{residual / amplitude if amplitude else float('nan'):9.3f} {cycles:7.2f}")
            rows.append({"phase_index": index, "band_m": band, "amplitude": amplitude,
                         "residual": residual, "ratio": residual / amplitude if amplitude else None,
                         "cycles": cycles})
    (WORK / "leakage.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("\nreading: a ratio that grows with the phase index in one band, while the other band's stays put,")
    print("         is the signature of a non-integer number of cycles in the window (leakage).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
