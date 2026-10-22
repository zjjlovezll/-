"""Tests for the independent contact references.

These are the only tests in the suite whose expected values come from outside the
solver, so they are written against hand-computed numbers rather than against a
recorded output.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.contact_reference import (
    EVIDENCE_LEVELS,
    ReferenceContact,
    circle_line_contact,
    circle_through,
    finer_grid_reference,
    hertz_from_reference,
    hertz_point_force,
    hertz_point_stiffness,
)

E_STAR = 1.1393e11


def test_hertz_point_force_matches_hand_value() -> None:
    # R* = 0.5 m, delta = 1 mm, E* = 1.1393e11 Pa
    expected = (4.0 / 3.0) * E_STAR * math.sqrt(0.5) * (1.0e-3) ** 1.5
    assert hertz_point_force(0.5, 1.0e-3, E_STAR) == pytest.approx(expected, rel=1e-12)
    assert hertz_point_force(0.5, 0.0, E_STAR) == 0.0


def test_hertz_stiffness_agrees_with_force_at_unit_penetration() -> None:
    for radius in (0.3, 0.5, 0.7):
        assert hertz_point_stiffness(radius, E_STAR) == pytest.approx(
            hertz_point_force(radius, 1.0, E_STAR), rel=1e-12)


def test_circle_through_recovers_a_known_circle() -> None:
    centre_y, centre_z, radius = 0.25, -0.75, 0.4
    angles = np.array([-0.2, 0.0, 0.25])
    y = centre_y + radius * np.cos(angles)
    z = centre_z + radius * np.sin(angles)
    got_y, got_z, got_r = circle_through(y, z)
    assert (got_y, got_z) == pytest.approx((centre_y, centre_z), abs=1e-12)
    assert got_r == pytest.approx(radius, rel=1e-12)


def test_circle_through_rejects_colinear_points() -> None:
    with pytest.raises(ValueError, match="colinear"):
        circle_through(np.array([0.0, 1.0, 2.0]), np.array([0.0, 1.0, 2.0]))


def test_circle_line_contact_matches_hand_computation() -> None:
    # Wheel R = 0.43 with centre 0.43 above the crown, rail crown R = 0.30 whose centre
    # sits 0.30 below its own surface. Overlap = 0.5 mm.
    reference = circle_line_contact(
        wheel_centre_y_m=0.0, wheel_centre_z_m=0.43, wheel_radius_m=0.43,
        rail_centre_y_m=0.0, rail_centre_z_m=-0.30, rail_radius_m=0.30)
    assert reference.penetration_m == pytest.approx(0.43 + 0.30 - 0.73, abs=1e-12)
    assert reference.penetration_m == pytest.approx(0.0, abs=1e-12)
    assert reference.radius_star_m == pytest.approx(0.43 * 0.30 / 0.73, rel=1e-12)
    assert reference.evidence == "analytic"
    assert reference.y_m == pytest.approx(0.0, abs=1e-12)


def test_circle_line_contact_penetration_when_pressed_in() -> None:
    reference = circle_line_contact(
        wheel_centre_y_m=0.0, wheel_centre_z_m=0.4295, wheel_radius_m=0.43,
        rail_centre_y_m=0.0, rail_centre_z_m=-0.30, rail_radius_m=0.30)
    assert reference.penetration_m == pytest.approx(0.0005, abs=1e-9)


def test_circle_line_contact_reports_separation_instead_of_contact() -> None:
    reference = circle_line_contact(
        wheel_centre_y_m=0.0, wheel_centre_z_m=0.4310, wheel_radius_m=0.43,
        rail_centre_y_m=0.0, rail_centre_z_m=-0.30, rail_radius_m=0.30)
    assert reference.penetration_m == 0.0
    assert "no contact" in reference.note


def test_hertz_from_reference_attaches_the_closed_form_force() -> None:
    geometric = circle_line_contact(
        wheel_centre_y_m=0.0, wheel_centre_z_m=0.4295, wheel_radius_m=0.43,
        rail_centre_y_m=0.0, rail_centre_z_m=-0.30, rail_radius_m=0.30)
    loaded = hertz_from_reference(geometric, E_STAR)
    expected = hertz_point_force(geometric.radius_star_m, geometric.penetration_m, E_STAR)
    assert loaded.normal_force_n == pytest.approx(expected, rel=1e-12)
    assert loaded.evidence == "analytic"


def test_finer_grid_reference_finds_a_known_minimum() -> None:
    # Rail crown as a parabola of radius 0.3 m; wheel as a flat plane 0.2 mm above it.
    rail_y = np.linspace(-0.02, 0.02, 2001)
    rail_z = -rail_y ** 2 / (2.0 * 0.30)
    wheel_y = np.array([-0.02, 0.02])
    wheel_z = np.array([-0.0002, -0.0002])
    reference = finer_grid_reference(wheel_y, wheel_z, rail_y, rail_z, samples=200001)
    assert reference.evidence == "finer_grid"
    assert reference.y_m == pytest.approx(0.0, abs=2e-4)
    assert reference.penetration_m == pytest.approx(2.0e-4, rel=5e-3)


def test_finer_grid_reference_needs_a_fine_grid() -> None:
    with pytest.raises(ValueError, match="at least 1001"):
        finer_grid_reference(np.array([0.0]), np.array([0.0]),
                             np.array([0.0]), np.array([0.0]), samples=11)


def test_evidence_levels_are_declared() -> None:
    assert EVIDENCE_LEVELS == ("analytic", "finer_grid", "literature")
    assert ReferenceContact("x", "analytic", 0.0, 0.0, None, None).evidence == "analytic"
