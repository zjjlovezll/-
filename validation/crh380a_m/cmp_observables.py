"""Compare two observables for the same parameter direction: peak force vs full waveform.

Builds the finite-difference column d(observation)/d(ln k_z) from the existing fleet pair
(0.85x, 1.15x) and reports the column norm, which sets the parameter uncertainty for a
given measurement noise (sigma_theta = sigma_noise / ||column||).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from velch.inverse.identifiability import Sensitivity, analyse

ROOT = Path(r"F:\velch_tmp\fleet")
CHANNEL = "axle1_right_normal_n"
LOW, HIGH = "fleet_00_k0.85c0.85", "fleet_02_k1.15c1.15"
SPAN = 0.30  # ln(1.15) - ln(0.85)


def series(name: str) -> np.ndarray:
    history = ROOT / name / "history.csv"
    with history.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return np.array([float(row[CHANNEL]) for row in rows])


low, high = series(LOW), series(HIGH)
count = min(low.size, high.size)
difference = (high[:count] - low[:count]) / SPAN

peak_low, peak_high = float(low.max()), float(high.max())
peak_column = np.array([[-(peak_high - peak_low) / SPAN]])  # sign irrelevant for norms
wave_column = (-difference).reshape(-1, 1)

print(f"samples {count}")
print(f"peak observable      : dPeak/dlnk = {abs(peak_column[0, 0]):.3f} kN per ln-unit")
print(f"waveform observable  : |column| = {np.linalg.norm(wave_column):.1f} kN per ln-unit")
print(f"gain factor          : {np.linalg.norm(wave_column) / abs(peak_column[0, 0]):.1f}x")

for label, column in (("peak", peak_column), ("waveform", wave_column)):
    scales = tuple([1.0e3] * column.shape[0])
    verdict = analyse(Sensitivity(("rail_k_z",), column, scales))
    print(f"{label:<9} rank={verdict.rank} cond={verdict.condition_number:.3e} "
          f"identifiable={verdict.identifiable['rail_k_z']} "
          f"coverage={verdict.coverage['rail_k_z']}")

sigma_noise = 1.0e3  # 1 kN
for label, column in (("peak", peak_column), ("waveform", wave_column)):
    print(f"{label:<9} sigma(ln k_z) for 1 kN noise = "
          f"{sigma_noise / np.linalg.norm(column):.4f}")
