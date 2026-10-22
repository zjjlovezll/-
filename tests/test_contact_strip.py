"""Tests for the strip-integral normal law (roadmap stage S1-d)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.contact import (ContactParameters, find_graph_contact, find_strip_contact)
from velch.profiles import GraphProfile, ProfileSample

E_STAR = 1.1393e11
WHEEL_CENTRE_Z = 0.430


def _wheel_flat(z_abs: float = 0.0, half_span: float = 0.010) -> GraphProfile:
    y = np.linspace(0.750 - half_span, 0.750 + half_span, 401)
    return GraphProfile(y_m=y, z_m=np.full_like(y, z_abs - WHEEL_CENTRE_Z),
                        source_sha256="test", source="test")


def _rail(z: np.ndarray, y: np.ndarray) -> GraphProfile:
    return GraphProfile(y_m=y, z_m=z, source_sha256="test", source="test")


def _sample(profile: GraphProfile) -> ProfileSample:
    return ProfileSample(profile=profile, dz_ds=np.zeros_like(profile.y_m),
                         lower_s_m=0.0, upper_s_m=1.0, selected_ids=("test",))


def _args():
    return dict(wheel_y_m=0.0, wheel_z_m=WHEEL_CENTRE_Z, wheel_roll_rad=0.0,
                wheel_lateral_offset_m=0.0, rail_y_m=0.0, rail_z_m=0.0)


def test_strip_integral_reproduces_its_own_force():
    y = np.linspace(0.741, 0.759, 181)
    rail = _rail(np.full_like(y, 1.0e-4), y)
    contact = find_strip_contact(_wheel_flat(), _sample(rail), **_args(),
                                 effective_modulus_pa=E_STAR)
    assert contact is not None
    # engaged over the whole 18 mm overlap, flat-on-flat
    expected = 0.25 * math.pi * E_STAR * 1.0e-4 * 0.018
    assert contact.stiffness_n_m_1p5 * contact.penetration_m ** 1.5 == pytest.approx(
        expected, rel=0.02)
    assert contact.half_width_m == pytest.approx(0.009, rel=0.02)


def test_strip_integral_keeps_load_on_the_shoulders_of_a_notch():
    y = np.linspace(0.740, 0.760, 401)
    z = np.where(np.abs(y - 0.750) < 0.004, -1.0e-3, 2.0e-4)
    rail = _rail(z, y)
    strip = find_strip_contact(_wheel_flat(), _sample(rail), **_args(),
                               effective_modulus_pa=E_STAR)
    point = find_graph_contact(_wheel_flat(), _sample(rail), **_args(),
                               stiffness_policy="local_circular",
                               effective_modulus_pa=E_STAR)
    assert strip is not None and point is not None
    strip_force = strip.stiffness_n_m_1p5 * strip.penetration_m ** 1.5
    point_force = point.stiffness_n_m_1p5 * point.penetration_m ** 1.5
    # Both see the 0.2 mm shoulder interference, but only the strip law carries it
    # over the engaged width; the point law puts it all on one node. The exact
    # ratio depends on the local curvature, so only the order is asserted.
    assert strip_force > 0.0
    ratio = strip_force / point_force
    assert 0.2 < ratio < 0.8, ratio


def test_strip_integral_returns_none_when_nothing_is_engaged():
    y = np.linspace(0.741, 0.759, 181)
    rail = _rail(np.full_like(y, -1.0e-4), y)   # 0.1 mm clear of the wheel
    assert find_strip_contact(_wheel_flat(), _sample(rail), **_args(),
                              effective_modulus_pa=E_STAR) is None


def test_strip_integral_requires_the_effective_modulus():
    y = np.linspace(0.741, 0.759, 181)
    rail = _rail(np.full_like(y, 1.0e-4), y)
    with pytest.raises(ValueError):
        find_strip_contact(_wheel_flat(), _sample(rail), **_args())


def test_strip_policy_name_is_validated():
    with pytest.raises(ValueError):
        ContactParameters(
            normal_model="hertz_effective_radius", damping_model="delta_half_velocity",
            tangential_model="sditt_cubic_saturation", effective_modulus_pa=E_STAR,
            effective_radius_m=0.54, normal_damping_n_s_m_1p5=1.0e6,
            friction_coefficient=0.4, creep_stiffness_x_n=1.0e6,
            creep_stiffness_lateral_n=1.0e6, reference_speed_floor_m_s=0.1,
            normal_policy="strips",
        )
