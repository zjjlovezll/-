"""Tests for the patch-scale geometry policy (roadmap stage S1-c)."""

from __future__ import annotations

import numpy as np
import pytest

from velch.contact import ContactParameters, find_graph_contact, find_patch_contact
from velch.profiles import GraphProfile, ProfileSample

WHEEL_CURVATURE = 2.0      # z'' of the wheel band, 1/m
RAIL_CURVATURE = 1.0       # z'' of the rail band, 1/m
APEX_M = 0.7500
WHEEL_APEX_Z = -0.430 - 2.0e-4   # wheel band apex: 0.2 mm below the rail crown


def _band(z_apex: float, curvature: float, half_span: float = 0.012,
          points: int = 1201) -> GraphProfile:
    y = np.linspace(APEX_M - half_span, APEX_M + half_span, points)
    # z = z_apex + (curvature/2) * (y - apex)^2, so z'' == curvature
    z = z_apex + 0.5 * curvature * (y - APEX_M) ** 2
    return GraphProfile(y_m=y, z_m=z, source_sha256="test", source="test")


def _sample(profile: GraphProfile) -> ProfileSample:
    return ProfileSample(profile=profile, dz_ds=np.zeros_like(profile.y_m),
                         lower_s_m=0.0, upper_s_m=1.0, selected_ids=("test",))


def _args(**overrides):
    args = dict(wheel_y_m=0.0, wheel_z_m=0.430, wheel_roll_rad=0.0,
                wheel_lateral_offset_m=0.0, rail_y_m=0.0, rail_z_m=0.0)
    args.update(overrides)
    return args


def test_unknown_geometry_policy_is_rejected():
    with pytest.raises(ValueError):
        ContactParameters(
            normal_model="hertz_effective_radius", damping_model="delta_half_velocity",
            tangential_model="sditt_cubic_saturation", effective_modulus_pa=1.0e11,
            effective_radius_m=0.54, normal_damping_n_s_m_1p5=1.0e6,
            friction_coefficient=0.4, creep_stiffness_x_n=1.0e6,
            creep_stiffness_lateral_n=1.0e6, reference_speed_floor_m_s=0.1,
            geometry_policy="not_a_policy",
        )


def test_patch_contact_lands_on_the_analytic_extremum():
    # The wheel sits 0.2 mm below its nominal position, so the apex penetrates.
    wheel = _band(WHEEL_APEX_Z, WHEEL_CURVATURE)
    rail = _band(0.0, RAIL_CURVATURE)
    contact = find_patch_contact(wheel, _sample(rail), **_args(),
                                 effective_modulus_pa=1.1393e11)
    assert contact is not None
    assert contact.y_m == pytest.approx(APEX_M, abs=1e-9)
    assert contact.penetration_m == pytest.approx(2.0e-4, rel=1e-6)
    radius_y = 0.430 - contact.wheel_z_m
    expected = 4.0 / (1.0 / radius_y + WHEEL_CURVATURE + RAIL_CURVATURE)
    assert contact.radius_star_m == pytest.approx(expected, rel=1e-9)
    assert contact.stiffness_n_m_1p5 == pytest.approx(
        4.0 / 3.0 * 1.1393e11 * float(np.sqrt(expected)), rel=1e-12)
    assert contact.edge_limited is False


def test_patch_contact_is_not_snapped_to_a_sampling_node():
    # Shift the apex by 0.37 of a node so a node cannot sit on it.
    spacing = 0.012 * 2.0 / 1200
    offset = 0.37 * spacing
    y = np.linspace(APEX_M - 0.012, APEX_M + 0.012, 1201)
    wheel = GraphProfile(y_m=y, z_m=WHEEL_APEX_Z + 0.5 * WHEEL_CURVATURE * (y - APEX_M - offset) ** 2,
                         source_sha256="test", source="test")
    rail = GraphProfile(y_m=y + 0.5 * spacing,
                        z_m=0.5 * RAIL_CURVATURE * (y + 0.5 * spacing - APEX_M - offset) ** 2,
                        source_sha256="test", source="test")
    contact = find_patch_contact(wheel, _sample(rail), **_args())
    assert contact is not None
    assert abs(contact.y_m - (APEX_M + offset)) < 1e-6


def test_patch_and_grid_agree_when_the_apex_is_a_node():
    wheel = _band(WHEEL_APEX_Z, WHEEL_CURVATURE)
    rail = _band(0.0, RAIL_CURVATURE)
    grid = find_graph_contact(wheel, _sample(rail), **_args(),
                              stiffness_policy="local_circular",
                              effective_modulus_pa=1.1393e11)
    patch = find_graph_contact(wheel, _sample(rail), **_args(),
                               stiffness_policy="local_circular",
                               effective_modulus_pa=1.1393e11,
                               geometry_policy="patch")
    assert grid is not None and patch is not None
    assert patch.penetration_m == pytest.approx(grid.penetration_m, abs=2e-7)
    assert patch.y_m == pytest.approx(grid.y_m, abs=1e-6)
