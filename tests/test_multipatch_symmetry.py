"""A3 guard: the default strip law is multi-patch and reports the force-weighted
centroid, not the deepest node.

The measurement (``validation/crh380a_m/probe_multipatch.py``) shows that on real
turnout cross-sections only one engaged region ever occurs at these penetrations
(0 / 720 poses).  These tests pin the structural behaviour that makes that safe:
when two shoulders *are* engaged, both count, and the contact point sits between
them.
"""

from __future__ import annotations

import numpy as np
import pytest

from velch.contact import find_strip_contact
from velch.profiles import GraphProfile, ProfileSample

E_STAR = 1.1393e11
WHEEL_CENTRE_Z = 0.430


def _wheel_flat(z_abs: float = 0.0, half_span: float = 0.010) -> GraphProfile:
    y = np.linspace(0.750 - half_span, 0.750 + half_span, 401)
    return GraphProfile(
        y_m=y,
        z_m=np.full_like(y, z_abs - WHEEL_CENTRE_Z),
        source_sha256="test",
        source="test",
    )


def _sample(profile: GraphProfile) -> ProfileSample:
    return ProfileSample(
        profile=profile,
        dz_ds=np.zeros_like(profile.y_m),
        lower_s_m=0.0,
        upper_s_m=1.0,
        selected_ids=("test",),
    )


def _two_shoulder_rail() -> GraphProfile:
    """Two flush shoulders (z = +0.2 mm) with a 1 mm deep, 8 mm wide notch."""
    y = np.linspace(0.740, 0.760, 401)
    z = np.where(np.abs(y - 0.750) < 0.004, -1.0e-3, 2.0e-4)
    return GraphProfile(y_m=y, z_m=z, source_sha256="test", source="test")


def _call(rail: GraphProfile, **kwargs):
    return find_strip_contact(
        _wheel_flat(),
        _sample(rail),
        wheel_y_m=0.0,
        wheel_z_m=WHEEL_CENTRE_Z,
        wheel_roll_rad=0.0,
        wheel_lateral_offset_m=0.0,
        rail_y_m=0.0,
        rail_z_m=0.0,
        effective_modulus_pa=E_STAR,
        **kwargs,
    )


def test_default_strip_law_carries_both_shoulders() -> None:
    contact = _call(_two_shoulder_rail())
    assert contact is not None
    # Symmetric shoulders -> the force-weighted centroid is the notch centre, not
    # either shoulder's deepest node.
    assert contact.y_m == pytest.approx(0.750, abs=2.0e-5)
    # Both shoulders are 6 mm, so the engaged width is ~12 mm.
    assert contact.half_width_m == pytest.approx(0.0062, rel=0.06)


def test_clipping_to_the_deepest_run_drops_the_far_shoulder() -> None:
    """The opt-in bounded window (A1 ``run`` policy) is the only path that can lose
    a patch; it must be visibly different so nobody turns it on by accident."""
    clipped = _call(_two_shoulder_rail(), clip_to_engaged_run=True)
    assert clipped is not None
    assert abs(clipped.y_m - 0.750) > 3.0e-3
    assert clipped.half_width_m < 0.0055


def test_asymmetric_shoulders_put_the_centroid_off_centre() -> None:
    y = np.linspace(0.740, 0.760, 401)
    # Left shoulder 0.2 mm, right shoulder 0.5 mm: the right one carries more.
    z = np.where(np.abs(y - 0.750) < 0.004, -1.0e-3, np.where(y < 0.750, 2.0e-4, 5.0e-4))
    rail = GraphProfile(y_m=y, z_m=z, source_sha256="test", source="test")
    contact = _call(rail)
    assert contact is not None
    assert contact.y_m > 0.750
