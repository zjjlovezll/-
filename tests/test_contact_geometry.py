"""Tests for the analytic spline contact path (roadmap stage S1)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.contact_geometry import (absolute_surfaces, curvature_at, fit_profile,
                                    swept_contact)


def _parabola(y0: float, z0: float, a: float, half_span: float = 0.010,
              samples: int = 401):
    ys = np.linspace(y0 - half_span, y0 + half_span, samples)
    return ys, z0 + a * (ys - y0) ** 2


def test_fit_reproduces_a_parabola_and_its_curvature():
    ys, zs = _parabola(0.75, 0.0, 3.0)
    surface = fit_profile(ys, zs, max_residual_m=1e-8, name="parabola")
    assert surface.max_residual_m < 1e-8
    assert surface.z(0.75) == pytest.approx(0.0, abs=1e-12)
    assert surface.dz(0.75) == pytest.approx(0.0, abs=1e-9)
    assert curvature_at(surface, 0.75, half_span_m=1.0e-3) == pytest.approx(6.0, rel=1e-6)


def test_swept_contact_matches_the_circular_hertz_equivalent():
    # Wheel curvature 1.0 1/m, rail curvature 0.5 1/m: the wheel is the sharper
    # body, so the deepest interference sits at the shared apex, as it does on an
    # ordinary tread contact.
    wheel_y, wheel_z = _parabola(0.750, -2.0e-4, 1.0)
    rail_y, rail_z = _parabola(0.750, 0.0, 0.5)
    wheel = fit_profile(wheel_y, wheel_z, max_residual_m=1e-8, name="wheel")
    rail = fit_profile(rail_y, rail_z, max_residual_m=1e-8, name="rail")
    contact = swept_contact(wheel, rail, wheel_origin_y_m=0.7465,
                            wheel_origin_z_m=0.430,
                            effective_modulus_pa=1.1393e11)
    assert contact is not None
    assert contact.y_m == pytest.approx(0.750, abs=1e-6)
    assert contact.penetration_m == pytest.approx(2.0e-4, rel=1e-6)
    radius_y = 0.430 - contact.wheel_z_m
    # z = a y^2 has z'' = 2a = 1/R, so the two bands contribute 2.0 and 1.0 1/m.
    expected = 4.0 / (1.0 / radius_y + 2.0 * 1.0 + 2.0 * 0.5)
    assert contact.radius_star_m == pytest.approx(expected, rel=1e-9)
    assert contact.stiffness_n_m_1p5 == pytest.approx(
        4.0 / 3.0 * 1.1393e11 * math.sqrt(expected), rel=1e-12)
    assert contact.half_width_m == pytest.approx(
        math.sqrt(2.0 * expected * 2.0e-4), rel=1e-9)
    assert contact.lever_y_m == pytest.approx(0.750 - 0.7465, abs=1e-6)
    assert contact.edge_limited is False


def test_zero_clearance_reports_no_penetration():
    wheel_y, wheel_z = _parabola(0.750, 0.0, 1.0)
    rail_y, rail_z = _parabola(0.750, 0.0, 0.5)
    wheel = fit_profile(wheel_y, wheel_z, max_residual_m=1e-8)
    rail = fit_profile(rail_y, rail_z, max_residual_m=1e-8)
    contact = swept_contact(wheel, rail, wheel_origin_y_m=0.7465,
                            wheel_origin_z_m=0.430)
    assert contact is not None
    assert contact.penetration_m == 0.0
    assert contact.half_width_m == 0.0


def test_fit_rejects_a_discontinuous_profile():
    ys = np.linspace(0.0, 0.02, 200)
    zs = np.zeros_like(ys)
    zs[100:] = 1.0e-3  # a step the spline cannot follow within 2 um
    with pytest.raises(ValueError):
        fit_profile(ys, zs, max_residual_m=2.0e-6, name="step")


def test_absolute_surfaces_applies_the_same_roll_as_the_grid_path():
    ys = np.array([-0.001, 0.0, 0.001])
    zs = np.array([0.0001, 0.0, 0.0001])

    class _Profile:
        y_m = ys
        z_m = zs

    class _Sample:
        profile = _Profile()

    roll = 0.02
    c, s = math.cos(roll), math.sin(roll)
    wy, wz, _ry, _rz = absolute_surfaces(_Profile(), _Sample(), wheel_y_m=0.7465,
                                         wheel_z_m=0.430, wheel_roll_rad=roll,
                                         wheel_lateral_offset_m=0.0,
                                         rail_y_m=0.753, rail_z_m=0.0)
    assert wy == pytest.approx(0.7465 + np.array([-0.001 * c - 0.0001 * s,
                                                 0.0,
                                                 0.001 * c - 0.0001 * s]))
    assert wz == pytest.approx(0.430 + np.array([-0.001 * s + 0.0001 * c,
                                                 0.0,
                                                 0.001 * s + 0.0001 * c]))


