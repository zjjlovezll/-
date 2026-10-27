"""A line of fixed wavelength, sampled while the speed changes, must come back at that wavelength.

This is the check the whole order-tracking idea rests on: a fixed-frequency projection of a record whose
speed swings from 1 to 85 km/h is meaningless, while a projection in the mileage domain is not.  The
synthetic case makes that concrete -- one 27.5 mm cosinusoid on a rail, sampled at the times a vehicle
passing with a prescribed speed profile would sample it, then resampled by mileage.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import s17_order_tracking as tracker  # noqa: E402


def _sampled_record(wavelength_m: float, amplitude: float, *, span_m: float = 55.0) -> tuple[np.ndarray, np.ndarray]:
    """A vehicle whose speed ramps over the span, sampling the rail at a constant 4 kHz.

    The span is a whole number of wavelengths (2000 x 27.5 mm) on purpose: a coherent projection over a
    fractional number of cycles reports an amplitude biased low, which this project already paid for once
    when it fitted whole-period blocks in the harmonic inverter.
    """

    rate_hz = 4000.0
    speed = np.linspace(3.0, 20.0, 6000)          # m/s over the run
    position = np.concatenate(([0.0], np.cumsum(speed / rate_hz)))
    inside = position <= span_m
    position = position[inside]
    time = np.arange(position.size) / rate_hz
    del time
    signal = amplitude * np.cos(2.0 * np.pi * position / wavelength_m)
    return position, signal


def test_the_spatial_peak_is_the_wavelength_that_was_written() -> None:
    position, signal = _sampled_record(0.0275, 0.8)
    grid, values = tracker.spatial_profile(position, signal, tracker.STEP_M)
    wavelengths, spectrum = tracker.spatial_spectrum(grid, values)
    inside = (wavelengths >= 0.018) & (wavelengths <= 0.040) & np.isfinite(wavelengths)
    peak = wavelengths[inside][int(np.argmax(spectrum[inside]))]
    assert peak == pytest.approx(0.0275, rel=0.08)


def test_the_coherent_amplitude_survives_when_the_speed_changes() -> None:
    """A fixed-time-frequency projection smears this record; the mileage projection does not.

    The rail carries one 27.5 mm cosinusoid.  A vehicle speeding up from 3 to 20 m/s samples it at a
    frequency that drifts over a factor of seven, so fitting one frequency in time is the wrong operator --
    while the same fit in the mileage domain sees exactly the wave that is on the rail.
    """

    wavelength = 0.0275
    amplitude = 0.8
    grid = np.arange(0.0, wavelength * 500.0, wavelength / 8.0)     # 500 whole periods
    values = amplitude * np.cos(2.0 * np.pi * grid / wavelength)

    # The same physics seen in time: speed ramps from 3 to 20 m/s, so dt per sample changes.
    speed = np.linspace(3.0, 20.0, grid.size)
    time = np.concatenate(([0.0], np.cumsum(np.diff(grid) / speed[:-1])))
    mean_frequency = float(np.mean(speed)) / wavelength
    basis = np.column_stack([np.cos(2.0 * np.pi * mean_frequency * time),
                             np.sin(2.0 * np.pi * mean_frequency * time)])
    coefficients, *_ = np.linalg.lstsq(basis, values, rcond=None)
    time_domain = float(np.hypot(coefficients[0], coefficients[1]))

    assert tracker.coherent_at(grid, values, wavelength) == pytest.approx(amplitude, rel=1e-6)
    assert time_domain < 0.5 * amplitude, (
        f"a single time frequency recovered {time_domain:.3f} of {amplitude}, so this test no longer "
        "demonstrates why order tracking is required"
    )


def test_a_spatial_sinusoid_is_invisible_at_four_times_its_wavelength() -> None:
    """The off-wavelength answer is near zero, so the depth is not a boxed average of the record."""

    position, signal = _sampled_record(0.0275, 0.8)
    grid, values = tracker.spatial_profile(position, signal, tracker.STEP_M)
    assert tracker.coherent_at(grid, values, 0.110) < 0.05 * tracker.coherent_at(grid, values, 0.0275)


def test_duplicate_mileage_is_trimmed_instead_of_breaking_the_interpolation() -> None:
    """At standstill the recorded position repeats; np.interp would refuse a non-monotone axis."""

    position = np.array([0.0, 1.0, 1.0, 1.0, 2.0, 3.0])
    signal = np.array([0.0, 1.0, 1.0, 1.0, 2.0, 3.0])
    grid, values = tracker.spatial_profile(position, signal, 0.5)
    assert np.all(np.diff(grid) > 0.0)
    assert values.size == grid.size
    assert values[0] == pytest.approx(0.0)


def test_the_grid_starts_and_stops_on_whole_steps() -> None:
    position = np.linspace(0.003, 5.002, 1000)
    grid, _ = tracker.spatial_profile(position, np.zeros_like(position), 0.005)
    assert grid[0] == pytest.approx(0.005)
    assert abs((grid[-1] / 0.005) - round(grid[-1] / 0.005)) < 1e-9
