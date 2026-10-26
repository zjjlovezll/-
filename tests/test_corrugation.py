"""Tests for `velch.corrugation`: the analytic lift, its two runnable forms, and the density rule."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from velch.corrugation import (
    Corrugation,
    CorrugationError,
    alias_free_step_m,
    interpolation_gain,
    lifted_profile_text,
    required_step_m,
    station_mileages,
    write_station_table,
)

PRR = """! Simpack profile, units m
units.len = 'm'
type = 0
point.begin
  -0.04500000  -0.42800000
   0.00000000  -0.43000000
   0.04500000  -0.43500000
point.end
"""


def test_the_lift_is_a_cosine_sum_of_the_requested_harmonics() -> None:
    defect = Corrugation(period_m=0.050, depth_m=30.0e-6, harmonics=(1.0, 0.5, 0.25))
    value = defect.at(0.0125)  # a quarter period
    expected = 30.0e-6 * (math.cos(math.pi / 2) + 0.5 * math.cos(math.pi) + 0.25 * math.cos(3 * math.pi / 2))
    assert value == pytest.approx(expected, rel=1e-12)
    assert defect.peak_to_peak() == pytest.approx(2.0 * 30.0e-6 * 1.75)


def test_the_order_n_wavelength_and_frequency_follow_the_period() -> None:
    defect = Corrugation(period_m=0.05, depth_m=30e-6, harmonics=(1.0, 0.3))
    assert defect.wavelength_m(1) == pytest.approx(0.05)
    assert defect.wavelength_m(2) == pytest.approx(0.025)
    assert defect.frequency_hz(22.2222, 1) == pytest.approx(444.444, rel=1e-4)
    assert defect.frequency_hz(22.2222, 2) == pytest.approx(888.888, rel=1e-4)


def test_the_track_form_matches_the_analytic_lift() -> None:
    defect = Corrugation(period_m=0.05, depth_m=30e-6, harmonics=(1.0, 0.3))
    track = defect.track(start_m=10.0, periods=4, step_m=0.0025)
    assert len(track.s_m) == 81
    worst = np.max(np.abs(np.asarray(track.vertical_m) - np.array([defect.at(float(s)) for s in track.s_m])))
    assert worst < 1e-15
    assert np.allclose(track.lateral_m, 0.0)
    assert math.isclose(float(track.span_m[0]), 10.0)


def test_interpolation_gain_matches_a_measured_linear_interpolation() -> None:
    wavelength = 0.05
    for samples_per_period in (4, 8, 20):
        step = wavelength / samples_per_period
        # whole periods only, or the truncated record leaks and the fit is biased
        stations = np.arange(0, 40 * samples_per_period) * step
        lifts = np.sin(2.0 * math.pi * stations / wavelength)
        fine = np.arange(0.0, stations[-1], 1e-5)
        theta = 2.0 * math.pi * fine / wavelength
        basis = np.column_stack((np.cos(theta), np.sin(theta)))
        coefficients, *_ = np.linalg.lstsq(basis, np.interp(fine, stations, lifts), rcond=None)
        measured = math.hypot(*coefficients)
        # the fine grid stops one sample short of the last station, so the record
        # is not exactly a whole number of periods; 1e-4 is far tighter than any
        # spacing error we care about (the formula is right to ~1e-7 on an exact record)
        assert measured == pytest.approx(interpolation_gain(step, wavelength), abs=1e-4)


def test_required_step_inverts_the_gain_monotonically() -> None:
    for wavelength in (0.025, 0.05, 0.1):
        for tolerance in (0.01, 0.03, 0.05):
            step = required_step_m(wavelength, tolerance=tolerance)
            assert interpolation_gain(step, wavelength) == pytest.approx(1.0 - tolerance, abs=1e-6)
        assert required_step_m(wavelength, tolerance=0.01) < required_step_m(wavelength, tolerance=0.05)
    assert required_step_m(0.025, tolerance=0.03) == pytest.approx(0.00240, abs=1e-5)
    assert alias_free_step_m(0.05) == pytest.approx(0.025)


def test_the_profile_text_is_shifted_by_the_physical_lift_in_either_sign_convention() -> None:
    for z_sign in (-1.0, 1.0):
        raised = lifted_profile_text(PRR, 30e-6, z_sign=z_sign)
        original = [line.split() for line in PRR.splitlines() if line.strip().startswith(("-", "0"))]
        changed = [line.split() for line in raised.splitlines() if line.strip().startswith(("-", "0"))]
        for before, after in zip(original, changed):
            assert float(before[0]) == float(after[0])
            assert float(after[1]) - float(before[1]) == pytest.approx(30e-6 / z_sign, rel=1e-6, abs=1e-12)
    assert "units.len = 'm'" in lifted_profile_text(PRR, 30e-6)
    assert lifted_profile_text(PRR, 0.0) == pytest.approx(PRR) or lifted_profile_text(PRR, 0.0) == PRR


def test_the_station_table_starts_at_zero_and_reaches_past_the_run(tmp_path: Path) -> None:
    mileages = station_mileages(start_m=10.0, end_m=10.2, step_m=0.0025, run_end_m=20.0)
    assert mileages[0] == 0.0
    assert mileages[-1] == 20.0
    assert mileages == sorted(mileages)
    assert len(mileages) == len(set(mileages))


def test_writing_the_table_puts_the_lift_only_inside_the_patch(tmp_path: Path) -> None:
    defect = Corrugation(period_m=0.05, depth_m=30e-6)
    stations = write_station_table(
        PRR, defect, directory=tmp_path, start_m=10.0, end_m=10.2, step_m=0.01, run_end_m=14.0
    )
    assert stations[0][0] == 0.0
    first = stations[0][1].read_text(encoding="utf-8")
    assert first == lifted_profile_text(PRR, 0.0), "outside the patch the section must be untouched"
    inside = [path for mileage, path in stations if 10.0 < mileage < 10.2]
    assert inside, "the patch must produce dense stations"
    text = inside[0].read_text(encoding="utf-8")
    assert text != lifted_profile_text(PRR, 0.0)


def test_refusals_name_the_reason() -> None:
    with pytest.raises(CorrugationError, match="period_m"):
        Corrugation(period_m=0.0, depth_m=1e-6)
    with pytest.raises(CorrugationError, match="depth_m"):
        Corrugation(period_m=0.05, depth_m=0.0)
    with pytest.raises(CorrugationError, match="at least the fundamental"):
        Corrugation(period_m=0.05, depth_m=1e-6, harmonics=())
    with pytest.raises(CorrugationError, match="must not be negative"):
        Corrugation(period_m=0.05, depth_m=1e-6, harmonics=(1.0, -0.5))
    with pytest.raises(CorrugationError, match="every harmonic amplitude is zero"):
        Corrugation(period_m=0.05, depth_m=1e-6, harmonics=(0.0, 0.0))
    with pytest.raises(CorrugationError, match="tolerance"):
        required_step_m(0.05, tolerance=1.5)
    with pytest.raises(CorrugationError, match="z_sign"):
        lifted_profile_text(PRR, 1e-6, z_sign=0.0)
    with pytest.raises(CorrugationError, match="point block is missing"):
        lifted_profile_text("nothing here", 1e-6)
    with pytest.raises(CorrugationError, match="must reach past the patch end"):
        station_mileages(start_m=0.0, end_m=10.0, step_m=0.01, run_end_m=9.0)
