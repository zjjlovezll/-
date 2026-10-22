"""Tests for the segmented spline representation and contact on it."""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.contact_geometry import (
    fit_profile,
    fit_segmented,
    swept_contact,
)


def _parabola(y, y0=0.0, z0=0.0, a=40.0):
    return z0 + a * (y - y0) ** 2


def test_a_plain_parabola_needs_one_piece():
    y = np.linspace(-0.02, 0.02, 201)
    band = fit_segmented(y, _parabola(y), name="parabola")
    assert len(band.pieces) == 1
    for sample in (-0.013, 0.0, 0.011):
        assert band.z(sample) == pytest.approx(_parabola(np.array([sample]))[0], abs=1e-12)


def test_a_kink_forces_a_split_and_keeps_z_continuous():
    y = np.linspace(-0.02, 0.02, 401)
    seam = 0.004
    z = np.where(
        y < seam,
        _parabola(y, a=40.0),
        _parabola(y, y0=seam, z0=40.0 * seam * seam, a=900.0),
    )
    band = fit_segmented(y, z, max_residual_m=1.0e-7, name="kink")
    assert len(band.pieces) >= 2
    assert band.z(seam) == pytest.approx(40.0 * seam * seam, abs=2e-6)
    for left, right in zip(band.pieces[:-1], band.pieces[1:]):
        assert left.y_hi_m == pytest.approx(right.y_lo_m, abs=1e-12)


def test_segmented_and_single_agree_on_a_smooth_band():
    y = np.linspace(-0.01, 0.01, 301)
    z = _parabola(y, a=25.0)
    single = fit_profile(y, z)
    band = fit_segmented(y, z)
    for sample in np.linspace(-0.009, 0.009, 17):
        assert band.z(float(sample)) == pytest.approx(single.z(float(sample)), abs=1e-12)
        assert band.dz(float(sample)) == pytest.approx(single.dz(float(sample)), abs=1e-9)


def test_a_step_band_stays_covered_and_records_the_relaxed_overshoot():
    y = np.linspace(-0.02, 0.02, 400)
    z = np.zeros_like(y)
    z[150:260] = 1.0e-3  # a step no cubic can represent at the minimum node count
    band = fit_segmented(y, z, min_nodes=6, max_depth=2, name="step")
    # Coverage is total: no hole may be left in the band, or the contact search
    # would silently extrapolate through it.
    assert band.y_lo_m == pytest.approx(y[0], abs=1e-12)
    assert band.y_hi_m == pytest.approx(y[-1], abs=1e-12)
    for left, right in zip(band.pieces[:-1], band.pieces[1:]):
        assert left.y_hi_m == pytest.approx(right.y_lo_m, abs=1e-12)
    assert band.relaxed_residual_m
    assert band.max_residual_m > 2.0e-6


def test_swept_contact_on_segmented_bands_matches_the_grid_reference():
    wheel_y = np.linspace(-0.03, 0.03, 601)
    rail_y = np.linspace(-0.03, 0.03, 601)
    sink = 2.0e-4
    # A crowned tread on a flat rail: the interference is a downward parabola, so the
    # deepest point is unambiguous and the answer is the sink itself.
    wheel_z = _parabola(wheel_y, a=1.16) - sink   # r = 0.43 m
    rail_z = np.zeros_like(rail_y)
    wheel = fit_segmented(wheel_y, wheel_z, name="wheel")
    rail = fit_segmented(rail_y, rail_z, name="rail")
    contact = swept_contact(wheel, rail, wheel_origin_y_m=0.0,
                            wheel_origin_z_m=-sink, scan_step_m=1.0e-4)
    assert contact is not None
    assert contact.y_m == pytest.approx(0.0, abs=2.0e-5)
    # The wheel sits 0.43 above the crown, so the penetration is the sink itself.
    assert contact.penetration_m == pytest.approx(sink, rel=0.02)


def test_contact_can_land_in_the_second_piece():
    """The search must run over the whole band, not per piece."""
    y = np.linspace(-0.02, 0.02, 801)
    rail_y = np.linspace(-0.02, 0.02, 801)
    # Wheel: high ground on the left, a deep narrow well on the right.
    wheel_z = np.where(y < 0.008, -0.43 + 0.0 * y, -0.43 - 1.0e-3)
    smooth = np.convolve(wheel_z, np.ones(9) / 9.0, mode="same")
    wheel_z = np.where(np.abs(y) > 0.019, smooth, wheel_z)
    rail_z = np.zeros_like(rail_y)
    wheel = fit_segmented(y, wheel_z, name="wheel")
    rail = fit_segmented(rail_y, rail_z, name="rail")
    contact = swept_contact(wheel, rail, wheel_origin_y_m=0.0, wheel_origin_z_m=-0.43,
                            scan_step_m=1.0e-4)
    assert contact is not None
    assert contact.penetration_m > 0.9e-3
    assert contact.y_m > 0.008
    assert math.isfinite(contact.radius_star_m)
