"""Reproduce the campaign's own published numbers from the raw channel files.

    python check_measured_window.py <condition dir> <start s> <end s> [lowpass_hz]

The 2026-10-19 figure set documents, for ``10kmh-SP-1``, a passage window of
32.60-46.78 s and, inside it, displacement peaks CH09 +0.60..+0.82 mm,
CH10 -0.25..-0.35 mm, CH11 +0.49..+0.63 mm, CH13 +0.91..+1.13 mm, CH15 +-0.2 mm.
The published figures are low-pass filtered (10 Hz for displacement, 5 Hz for
acceleration) and CH10 carries a constant lateral offset that the figures remove,
so both are applied here before the comparison.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt

from velch.io.measured import CAMPAIGN_CHANNELS, read_channel

folder = Path(sys.argv[1])
start, end = float(sys.argv[2]), float(sys.argv[3])
lowpass_hz = float(sys.argv[4]) if len(sys.argv) > 4 else 10.0
by_channel = {item.channel: item for item in CAMPAIGN_CHANNELS}


def filtered(values: np.ndarray, dt: float) -> np.ndarray:
    if lowpass_hz <= 0.0:
        return values
    sos = butter(4, lowpass_hz / (0.5 / dt), btype="low", output="sos")
    return sosfiltfilt(sos, values)


print(f"window  : {start:.2f}..{end:.2f} s   low-pass {lowpass_hz:g} Hz   {folder.name}")
print(f"{'ch':<5}{'name':<28}{'unit':<5}{'min':>10}{'max':>10}{'|peak|':>10}")
for channel in (1, 9, 10, 11, 12, 13, 15):
    spec = by_channel[channel]
    time_s, values = read_channel(folder, channel)
    dt = float(np.median(np.diff(time_s)))
    mask = (time_s >= start) & (time_s <= end)
    window = filtered(values, dt)[mask]
    if channel == 10:
        window = window - float(np.median(window))
    peak = float(window[np.argmax(np.abs(window))])
    print(f"CH{channel:02d}  {spec.name:<28}{spec.unit:<5}"
          f"{window.min():10.3f}{window.max():10.3f}{peak:10.3f}")
