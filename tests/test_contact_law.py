"""Unit tests for the pluggable contact policies."""
from __future__ import annotations

import math

import numpy as np
import pytest

from velch.contact import ContactParameters
from velch.contact_law import (adaptive_theta_m, check_policy, circular_equivalent_radius,
                               hertz_half_width_m, hertz_stiffness_n_m_1p5,
                               hunt_crossley_coefficient, local_curvature,
                               soft_argmax_position)


def _base_parameters(**overrides) -> ContactParameters:
    values = dict(
        normal_model="hertz_effective_radius",
        damping_model="delta_half_velocity",
        tangential_model="sditt_cubic_saturation",
        effective_modulus_pa=1.1393e11,
        effective_radius_m=0.02,
        normal_damping_n_s_m_1p5=1.0e6,
        friction_coefficient=0.4,
        creep_stiffness_x_n=1.0e6,
        creep_stiffness_lateral_n=5.0e5,
        reference_speed_floor_m_s=0.1,
    )
    values.update(overrides)
    return ContactParameters(**values)


def test_defaults_reproduce_the_historic_law() -> None:
    p = _base_parameters()
    assert p.point_policy == "argmax"
    assert p.normal_stiffness_n_m_1p5 == pytest.approx(4.0 / 3.0 * 1.1393e11 * math.sqrt(0.02))
    assert p.damping_policy == "fixed_coefficient"


def test_unknown_policies_are_rejected() -> None:
    for field, bad in (("point_policy", "center"), ("stiffness_policy", "magic"),
                       ("damping_policy", "linear")):
        with pytest.raises(ValueError, match="unknown"):
            _base_parameters(**{field: bad})


def test_policy_bounds_are_validated() -> None:
    with pytest.raises(ValueError, match="point_theta_m"):
        _base_parameters(point_theta_m=0.0)
    with pytest.raises(ValueError, match="ellipticity_correction"):
        _base_parameters(ellipticity_correction=-1.0)
    with pytest.raises(ValueError, match="restitution_coefficient"):
        _base_parameters(restitution_coefficient=1.0)
    with pytest.raises(ValueError, match="damping_reference_speed"):
        _base_parameters(damping_reference_speed_m_s=0.0)


def test_check_policy_passes_known_names() -> None:
    assert check_policy("soft_argmax", ("argmax", "soft_argmax"), "point") == "soft_argmax"


def test_half_width_scales_with_the_square_root_of_penetration() -> None:
    assert hertz_half_width_m(0.0, 0.5) == 0.0
    assert hertz_half_width_m(0.0001, 0.5) == pytest.approx(math.sqrt(2 * 0.5 * 1e-4))
    assert hertz_half_width_m(0.0001, 0.5) / hertz_half_width_m(0.0004, 0.5) == pytest.approx(0.5)


def test_adaptive_theta_is_bounded_and_scales_with_the_patch() -> None:
    assert adaptive_theta_m(0.0) == pytest.approx(2.0e-6)
    assert adaptive_theta_m(0.01) == pytest.approx(5.0e-5)
    small = adaptive_theta_m(3.0e-6)
    large = adaptive_theta_m(1.0e-5)
    assert small < large
    assert 2.0e-6 <= small <= 5.0e-5


def test_soft_argmax_centroid_sits_between_the_peaks() -> None:
    grid = np.linspace(0.0, 1.0, 11)
    depth = np.zeros_like(grid)
    depth[3] = 1e-4
    depth[7] = 1e-4
    centroid = soft_argmax_position(grid, depth, 1e-5)
    assert centroid == pytest.approx(grid[5], abs=1e-9)
    heavier = depth.copy()
    heavier[7] = 2e-4
    assert soft_argmax_position(grid, heavier, 1e-5) > centroid


def test_soft_argmax_ignores_non_penetrating_part_of_the_grid() -> None:
    grid = np.linspace(0.0, 1.0, 11)
    depth = np.full_like(grid, -1e-3)
    depth[2] = 1e-4
    assert soft_argmax_position(grid, depth, 1e-5) == pytest.approx(grid[2], abs=1e-12)


def test_soft_argmax_returns_none_without_contact() -> None:
    grid = np.linspace(0.0, 1.0, 11)
    depth = np.full_like(grid, -1e-4)
    assert soft_argmax_position(grid, depth, 1e-5) is None


def test_local_curvature_recovers_a_parabola() -> None:
    grid = np.linspace(-0.01, 0.01, 401)
    curvature = 50.0
    z = 0.5 * curvature * grid ** 2
    assert local_curvature(z, grid, 0.0) == pytest.approx(curvature, rel=1e-6)
    assert local_curvature(z, grid, 0.005) == pytest.approx(curvature, rel=5e-2)


def test_local_curvature_is_zero_for_a_line() -> None:
    grid = np.linspace(-0.01, 0.01, 201)
    z = 0.01 * grid
    assert local_curvature(z, grid, 0.0) == pytest.approx(0.0, abs=1e-9)


def test_circular_equivalent_radius_follows_the_curvature_sum() -> None:
    r = circular_equivalent_radius(0.43, 0.0, 0.0)
    assert r == pytest.approx(4.0 * 0.43)
    softer = circular_equivalent_radius(0.43, 60.0, 2.5)
    assert softer < r
    assert circular_equivalent_radius(0.43, 0.0, 0.0, ellipticity=0.5) == pytest.approx(r * 0.5)


def test_local_stiffness_separates_tread_and_flange_root() -> None:
    # Tread: nearly flat laterally (17 m crown) against a 0.4 m rail crown.
    tread = circular_equivalent_radius(0.43, 1.0 / 17.0, 1.0 / 0.4)
    # Flange root: a sharp 15 mm lateral radius, i.e. a conformal contact.
    root = circular_equivalent_radius(0.43, 1.0 / 15e-3, 1.0 / 0.4)
    tread_stiffness = hertz_stiffness_n_m_1p5(1.1393e11, tread)
    root_stiffness = hertz_stiffness_n_m_1p5(1.1393e11, root)
    assert root < tread
    assert root_stiffness < tread_stiffness
    # The tread equivalent radius lands in the physical range and is far stiffer
    # than the historic 0.02 m placeholder.
    assert 0.2 < tread < 1.5
    assert tread_stiffness > hertz_stiffness_n_m_1p5(1.1393e11, 0.02)


def test_hunt_crossley_damping_scales_with_stiffness_and_vanishs_at_e_one() -> None:
    stiff = hertz_stiffness_n_m_1p5(1.1393e11, 0.5)
    soft = hunt_crossley_coefficient(stiff, 0.5, 0.5)
    assert soft > 0.0
    assert hunt_crossley_coefficient(stiff, 1.0, 0.5) == pytest.approx(0.0)
    assert hunt_crossley_coefficient(2 * stiff, 0.5, 0.5) == pytest.approx(2 * soft)
    with pytest.raises(ValueError, match="reference speed"):
        hunt_crossley_coefficient(stiff, 0.5, 0.0)
