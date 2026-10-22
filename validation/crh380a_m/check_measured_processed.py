"""Reproduce the campaign's published numbers through the library's own path.

    python check_measured_processed.py <condition dir> <start s> <end s>

Uses ``read_record(..., processed=True)`` (10 Hz displacement low-pass plus the
CH10 window-offset removal) and compares against the ranges published in
``E:\\齿轨测试数据\\出图\\30kmh_出图定稿_20261019\\处理说明.md`` for the 10 km/h
straight-passage run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from velch.io.measured import read_record

DOCUMENTED = {
    "disp_z_switch_point": (0.60, 0.82, "mm"),
    "disp_y_switch_point": (-0.35, -0.25, "mm"),
    "disp_z_lead_curve": (0.49, 0.63, "mm"),
    "disp_y_lead_curve": (0.08, 0.21, "mm"),
    "disp_z_frog": (0.91, 1.13, "mm"),
    "disp_y_frog": (-0.20, 0.20, "mm"),
}

folder = Path(sys.argv[1])
start, end = float(sys.argv[2]), float(sys.argv[3])
condition, time_s, columns, _ = read_record(
    folder, window=(start, end), unit_system="raw", processed=True)
print(f"{condition.label}  window {start:.2f}..{end:.2f} s  "
      f"{time_s.size} samples")
print(f"{'channel':<24}{'documented':>18}{'reproduced':>13}{'in range':>10}")
worst = 0.0
for name, (low, high, unit) in DOCUMENTED.items():
    values = columns[name]
    peak = float(values[np.argmax(np.abs(values))])
    inside = low - 1e-9 <= peak <= high + 1e-9
    worst = max(worst, abs(peak - min(max(peak, low), high)))
    print(f"{name:<24}{f'{low:+.2f}..{high:+.2f} {unit}':>18}"
          f"{peak:>13.3f}{'yes' if inside else 'NO':>10}")
print(f"worst distance to a documented bound: {worst:.3f}")
