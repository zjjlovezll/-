"""Measured-campaign conditioning: low-pass corner and offset removal."""

from __future__ import annotations

import numpy as np

from velch.io.measured import OFFSET_CHANNELS, PROCESSING_LOWPASS_HZ, lowpass


def test_lowpass_keeps_a_slow_signal_and_removes_a_fast_one() -> None:
    rate = 5120.0
    time = np.arange(int(rate), dtype=float) / rate
    slow = np.sin(2.0 * np.pi * 2.0 * time)
    fast = np.sin(2.0 * np.pi * 200.0 * time)

    kept = lowpass(slow, rate, 10.0)
    removed = lowpass(fast, rate, 10.0)

    # Judge by gain, not pointwise: a 10 Hz corner on a 5.12 kHz record has a long
    # impulse response, so both ends carry the zero-phase filter's startup transient.
    middle = slice(2048, -2048)
    gain = np.sqrt(np.mean(kept[middle] ** 2)) / np.sqrt(np.mean(slow[middle] ** 2))
    assert abs(gain - 1.0) < 0.02
    assert np.sqrt(np.mean(removed[middle] ** 2)) < 1e-3


def test_lowpass_preserves_a_short_record_and_rejects_a_corner_above_nyquist() -> None:
    values = np.arange(8, dtype=float)
    assert np.allclose(lowpass(values, 5120.0, 10.0), values)
    long_record = np.linspace(-1.0, 1.0, 4096)
    assert np.allclose(lowpass(long_record, 10.0, 10.0), long_record)


def test_campaign_processing_constants_match_the_documented_figure_set() -> None:
    # 处理说明.md: displacement figures at 10 Hz, acceleration figures at 5 Hz.
    assert PROCESSING_LOWPASS_HZ["displacement"] == 10.0
    assert PROCESSING_LOWPASS_HZ["acceleration"] == 5.0
    # CH10 swings +-22 mm outside the passage, so its published value is a window offset.
    assert "disp_y_switch_point" in OFFSET_CHANNELS
    assert "disp_y_frog" not in OFFSET_CHANNELS
