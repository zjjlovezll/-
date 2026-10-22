"""Band metrics must reproduce the measured campaign's convention, not a new one."""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.inverse.bands import (
    BandError,
    acceleration_from_position,
    band_metrics,
    band_rms,
    bandpass,
    third_octave_centres,
    third_octave_levels,
)

RATE = 2048.0


def _tone(frequency: float, amplitude: float = 1.0, seconds: float = 12.0) -> np.ndarray:
    time = np.arange(int(RATE * seconds)) / RATE
    return amplitude * np.sin(2.0 * math.pi * frequency * time)


def _interior(values: np.ndarray, seconds: float = 8.0) -> np.ndarray:
    """The part a passage window would actually use: away from both record ends."""

    rate = RATE
    margin = int(rate * (values.shape[0] / rate - seconds) / 2)
    return values[margin: values.shape[0] - margin]


def test_bandpass_removes_dc_and_keeps_a_tone_in_the_band() -> None:
    constant = np.full(int(RATE * 4.0), 5.0)
    assert band_rms(constant, RATE, 5.0, 1000.0) < 0.05

    kept = band_rms(_interior(_tone(200.0, amplitude=2.0)), RATE, 5.0, 1000.0)
    assert kept == pytest.approx(2.0 / math.sqrt(2.0), rel=0.10)


def test_bandpass_rejects_tones_outside_the_band() -> None:
    assert band_rms(_interior(_tone(2.0)), RATE, 5.0, 1000.0) < 0.10
    # the high edge must be tested inside Nyquist: a 1500 Hz tone at 2048 Hz would alias into
    # the band, which is a property of sampling, not of the filter
    assert band_rms(_interior(_tone(600.0)), RATE, 5.0, 200.0) < 0.10


def test_third_octave_centres_are_anchored_on_1000_hz_and_cover_the_band() -> None:
    centres = third_octave_centres(5.0, 1000.0)
    assert min(centres) <= 5.0 * (2.0 ** (1.0 / 3.0))
    assert max(centres) == pytest.approx(1000.0)
    ratios = [b / a for a, b in zip(centres, centres[1:])]
    assert all(r == pytest.approx(2.0 ** (1.0 / 3.0)) for r in ratios)


def test_dominant_band_follows_the_excitation_frequency() -> None:
    levels = third_octave_levels(_interior(_tone(400.0)), RATE)
    dominant = max(levels, key=lambda centre: levels[centre])
    assert 300.0 < dominant < 520.0


def test_band_metrics_report_peak_and_robust_companions() -> None:
    metrics = band_metrics(_interior(_tone(200.0, amplitude=2.0)), RATE)
    assert metrics.rms == pytest.approx(2.0 / math.sqrt(2.0), rel=0.10)
    # internal consistency: the reported peak-to-peak belongs to the same filtered series
    assert metrics.peak_to_peak == pytest.approx(2.0 * metrics.peak, rel=0.06)
    # a pure tone spreads |x| over its whole range, so median|x| < p99.9 <= peak
    assert metrics.median_abs < metrics.p999_abs <= metrics.peak + 1e-9


def test_acceleration_from_position_recovers_the_analytic_value() -> None:
    frequency, amplitude = 50.0, 1e-3
    time = np.arange(int(RATE), dtype=float) / RATE
    position = amplitude * np.sin(2.0 * math.pi * frequency * time)
    acceleration = acceleration_from_position(position, RATE)
    middle = slice(64, -64)
    expected = -(2.0 * math.pi * frequency) ** 2 * amplitude
    assert float(np.max(np.abs(acceleration[middle]))) == pytest.approx(abs(expected), rel=0.02)


def test_errors_are_explicit() -> None:
    with pytest.raises(BandError):
        third_octave_centres(0.0, 1000.0)
    with pytest.raises(BandError):
        bandpass(np.zeros(1000), 0.0)
    with pytest.raises(BandError):
        acceleration_from_position(np.zeros(2), RATE)
    with pytest.raises(BandError):
        bandpass(np.zeros((4, 4)), RATE)
