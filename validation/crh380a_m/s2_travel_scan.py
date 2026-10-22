import glob
import os

import numpy as np

for directory in sorted(glob.glob("out_*")):
    history = os.path.join(directory, "history.csv")
    if not os.path.exists(history):
        continue
    table = np.genfromtxt(history, delimiter=",", names=True)
    if table.dtype.names is None or "axle1_z_m" not in table.dtype.names:
        continue
    travel = np.ptp(table["axle1_z_m"]) * 1e3
    peak = 0.0
    for name in table.dtype.names:
        if name.startswith("axle1_") and name.endswith("_normal_n"):
            peak = max(peak, float(np.max(table[name])) / 1e3)
    print(f"{directory:34s} travel={travel:6.3f} mm  peak={peak:7.2f} kN  N={table.size:5d}")
