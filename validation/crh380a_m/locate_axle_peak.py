"""Locate the rear-axle over-penetration of the damped full run."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

path = Path(sys.argv[1] if len(sys.argv) > 1 else "out_full12_damp3e7")
with (path / "history.csv").open(encoding="utf-8") as handle:
    header = handle.readline().strip().split(",")
data = np.loadtxt(path / "history.csv", delimiter=",", skiprows=1)
column = {name: index for index, name in enumerate(header)}
time_s = data[:, column["time_s"]]

print(f"{'axle':>6}{'peak kN':>10}{'t s':>9}{'axle x m':>10}{'pen um':>9}"
      f"{'neighbour pen um':>18}")
for axle in range(1, 5):
    force = data[:, column[f"axle{axle}_right_normal_n"]]
    index = int(np.argmax(force))
    x_m = data[index, column[f"axle{axle}_x_m"]]
    pen = 1e6 * data[index, column[f"axle{axle}_right_penetration_m"]]
    others = " ".join(
        f"{1e6 * data[index, column[f'axle{other}_right_penetration_m']]:6.0f}"
        for other in range(1, 5)
        if other != axle
    )
    print(f"{axle:>6}{force[index] / 1e3:>10.1f}{time_s[index]:>9.4f}{x_m:>10.2f}"
          f"{pen:>9.0f}{others:>18}")

peak = data[:, column["axle1_right_normal_n"]].max()
first_lost = np.flatnonzero(data[:, column["axle1_right_normal_n"]] <= 0.0)
if first_lost.size:
    index = int(first_lost[0])
    print(f"\nfirst front-axle contact loss at t={time_s[index]:.4f} s, "
          f"x={data[index, column['axle1_x_m']]:.3f} m")
windows = []
right = data[:, column["axle1_right_normal_n"]]
lost = right <= 0.0
start = None
for index, flag in enumerate(lost):
    if flag and start is None:
        start = index
    elif not flag and start is not None:
        windows.append((time_s[start], time_s[index - 1],
                        data[start, column["axle1_x_m"]], data[index - 1, column["axle1_x_m"]]))
        start = None
if start is not None:
    windows.append((time_s[start], time_s[-1],
                    data[start, column["axle1_x_m"]], data[-1, column["axle1_x_m"]]))
print(f"front-axle loss windows: {len(windows)}")
for begin, end, first, last in windows:
    print(f"  t {begin:7.4f}..{end:7.4f} s   x {first:7.3f}..{last:7.3f} m")
