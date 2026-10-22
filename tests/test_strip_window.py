"""Bounded strip patch: a modelling window is not a geometric edge.

The whole-overlap strip law integrates every engaged strip, so a flangeway recess
or a seat cut adds to the normal force and drags the reported contact point off the
load-bearing crown.  ``strip_half_width_m`` bounds the integral.  The subtle part is
the ``edge_limited`` flag: it used to mean "the engaged band reaches the end of the
overlap", which was a genuine warning because the overlap *was* the geometry.  Once
the patch width is a choice, the window boundary is not an edge, and reporting it as
one failed the solver's ``no_edge_limited_active_contact`` gate on every bounded run.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.contact import find_strip_contact
from velch.profiles import GraphProfile, ProfileSample

E_STAR = 1.1393e11
WHEEL_CENTRE_Z = 0.430
DEPTH = 1.0e-4
SPAN = 0.018


def _wheel_flat(half_span: float = 0.010) -> GraphProfile:
    y = np.linspace(0.750 - half_span, 0.750 + half_span, 401)
    return GraphProfile(y_m=y, z_m=np.full_like(y, -WHEEL_CENTRE_Z),
                        source_sha256="test", source="test")


def _rail() -> GraphProfile:
    y = np.linspace(0.741, 0.759, 181)
    return GraphProfile(y_m=y, z_m=np.full_like(y, DEPTH),
                        source_sha256="test", source="test")


def _sample(profile: GraphProfile) -> ProfileSample:
    return ProfileSample(profile=profile, dz_ds=np.zeros_like(profile.y_m),
                         lower_s_m=0.0, upper_s_m=1.0, selected_ids=("test",))


def _args() -> dict[str, float]:
    return dict(wheel_y_m=0.0, wheel_z_m=WHEEL_CENTRE_Z, wheel_roll_rad=0.0,
                wheel_lateral_offset_m=0.0, rail_y_m=0.0, rail_z_m=0.0)


def _force(contact) -> float:
    return contact.stiffness_n_m_1p5 * contact.penetration_m ** 1.5


def test_unbounded_strip_flags_the_overlap_edges():
    contact = find_strip_contact(_wheel_flat(), _sample(_rail()), **_args(),
                                 effective_modulus_pa=E_STAR)
    assert contact is not None
    assert contact.edge_limited is True
    # The right-endpoint rectangle rule read as N strips of width span/(N-1), so the
    # discrete integral sits a few per mille above span*depth; 3 % is the tolerance.
    assert _force(contact) == pytest.approx(0.25 * math.pi * E_STAR * DEPTH * SPAN, rel=0.03)


def test_bounded_strip_does_not_flag_the_window_as_an_edge():
    contact = find_strip_contact(_wheel_flat(), _sample(_rail()), **_args(),
                                 center_y_m=0.750, half_width_m=0.002,
                                 effective_modulus_pa=E_STAR)
    assert contact is not None
    assert contact.edge_limited is False
    assert _force(contact) == pytest.approx(
        0.25 * math.pi * E_STAR * DEPTH * 2.0 * 0.002, rel=0.03)


def test_bounded_strip_is_narrower_than_the_overlap_force():
    wide = find_strip_contact(_wheel_flat(), _sample(_rail()), **_args(),
                              effective_modulus_pa=E_STAR)
    narrow = find_strip_contact(_wheel_flat(), _sample(_rail()), **_args(),
                                center_y_m=0.750, half_width_m=0.002,
                                effective_modulus_pa=E_STAR)
    assert wide is not None and narrow is not None
    assert _force(narrow) < 0.25 * _force(wide)


def test_bounded_strip_reports_its_own_half_width():
    contact = find_strip_contact(_wheel_flat(), _sample(_rail()), **_args(),
                                 center_y_m=0.750, half_width_m=0.002,
                                 effective_modulus_pa=E_STAR)
    assert contact is not None
    assert contact.half_width_m == pytest.approx(0.002, rel=0.05)


def test_window_outside_the_overlap_returns_none():
    contact = find_strip_contact(_wheel_flat(), _sample(_rail()), **_args(),
                                 center_y_m=0.900, half_width_m=0.002,
                                 effective_modulus_pa=E_STAR)
    assert contact is None


def _rail_with_notch() -> GraphProfile:
    """Two engaged shoulders split by a 3 mm relief notch (a flangeway in miniature)."""
    y = np.concatenate([
        np.linspace(0.741, 0.745, 41, endpoint=False),
        np.linspace(0.745, 0.755, 51, endpoint=False),
        np.linspace(0.755, 0.759, 41),
    ])
    z = np.empty_like(y)
    z[:41] = DEPTH
    z[41:91] = -5.0e-4
    z[91:] = 2.0 * DEPTH  # deeper shoulder: makes the "follow the deepest" rule observable
    return GraphProfile(y_m=y, z_m=z, source_sha256="test", source="test")


def test_run_policy_drops_the_second_engaged_shoulder():
    wheel = _wheel_flat()
    rail = _sample(_rail_with_notch())
    whole = find_strip_contact(wheel, rail, **_args(), effective_modulus_pa=E_STAR)
    run = find_strip_contact(wheel, rail, **_args(), clip_to_engaged_run=True,
                             effective_modulus_pa=E_STAR)
    assert whole is not None and run is not None
    assert _force(run) < 0.75 * _force(whole)
    assert run.half_width_m < 0.006


def test_run_policy_centres_on_the_shoulder_that_carries_the_load():
    contact = find_strip_contact(_wheel_flat(), _sample(_rail_with_notch()), **_args(),
                                 clip_to_engaged_run=True, effective_modulus_pa=E_STAR)
    assert contact is not None
    # The deeper shoulder sits at 0.755..0.759; the 4 mm one at 0.741..0.745 must be ignored.
    assert 0.755 <= contact.y_m <= 0.759
    assert contact.half_width_m < 0.003


def test_run_policy_still_flags_a_run_that_reaches_the_overlap_edge():
    # No notch: the engaged run is the whole overlap, so the warning must survive.
    contact = find_strip_contact(_wheel_flat(), _sample(_rail()), **_args(),
                                 clip_to_engaged_run=True, effective_modulus_pa=E_STAR)
    assert contact is not None
    assert contact.edge_limited is True


def test_contact_parameters_accept_the_run_policy():
    from velch.contact import ContactParameters

    params = ContactParameters(
        normal_model="hertz_effective_radius",
        damping_model="delta_half_velocity",
        tangential_model="sditt_cubic_saturation",
        effective_modulus_pa=E_STAR,
        effective_radius_m=0.02,
        normal_damping_n_s_m_1p5=1.0e6,
        friction_coefficient=0.4,
        creep_stiffness_x_n=1.0e6,
        creep_stiffness_lateral_n=5.0e5,
        reference_speed_floor_m_s=0.1,
        normal_policy="strip_integral",
        strip_center_policy="run",
    )
    assert params.strip_center_policy == "run"
    assert params.strip_half_width_m is None
