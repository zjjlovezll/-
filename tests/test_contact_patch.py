"""Tests for the discretised (patch-averaged) Hertz contact option."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from velch.contact import ContactParameters, _contact_on_span


def _params(**overrides) -> ContactParameters:
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


def _sample(profile_y: np.ndarray, dz_ds) -> SimpleNamespace:
    values = np.asarray(dz_ds, dtype=float)
    return SimpleNamespace(
        profile=SimpleNamespace(y_m=profile_y, dz_ds=values),
        dz_ds=values,
    )

def _flat_contact(*, rail_offset: float = 0.0, patch_half_width_m: float = 0.0,
                  patch_slices: int = 9):
    """A flat wheel tread laying on a flat rail, lowered by 0.5 mm."""
    y = np.linspace(-0.004, 0.004, 81)
    wheel_y = y.copy()
    wheel_z = np.full_like(y, -0.0005)
    rail_y = y.copy()
    rail_z = np.full_like(y, rail_offset)
    return _contact_on_span(
        wheel_y, wheel_z, _sample(y, np.zeros_like(y)), rail_y, rail_z,
        wheel_y_m=0.0, wheel_z_m=0.0, rail_y_m=0.0,
        lower=-0.004, upper=0.004,
        patch_half_width_m=patch_half_width_m, patch_slices=patch_slices,
    )


def test_patch_defaults_are_off():
    params = _params()
    assert params.patch_half_width_m == 0.0
    assert params.patch_enabled is False


def test_patch_rejects_an_even_slice_count():
    with pytest.raises(ValueError):
        _params(patch_slices=8)


def test_patch_rejects_a_negative_half_width():
    with pytest.raises(ValueError):
        _params(patch_half_width_m=-1e-3)


def test_patch_does_not_change_a_uniform_contact():
    point = _flat_contact()
    patch = _flat_contact(patch_half_width_m=0.0005)
    assert point is not None and patch is not None
    assert point.penetration_m == pytest.approx(0.0005, rel=1e-12)
    assert patch.penetration_m == pytest.approx(point.penetration_m, rel=1e-9)
    assert patch.y_m == pytest.approx(point.y_m)


def test_patch_softens_a_step_but_keeps_the_contact_alive():
    """At a rail step the point model reports the peak depth of one side only.

    The patch averages depth**1.5 over its own width, so on the same geometry it
    reports a smaller equivalent penetration - while staying strictly positive,
    which is what keeps the normal force from collapsing at a transfer.
    """
    y = np.linspace(-0.004, 0.004, 161)
    wheel_y = y.copy()
    wheel_z = np.full_like(y, -0.0005)
    rail_y = y.copy()
    # 0.8 mm higher running surface beyond y = 0: the deepest point sits inside.
    rail_z = np.where(y > 0.0, 0.0008, 0.0)
    sample = _sample(y, np.zeros_like(y))

    kwargs = dict(wheel_y_m=0.0, wheel_z_m=0.0, rail_y_m=0.0, lower=-0.004, upper=0.004)
    point = _contact_on_span(wheel_y, wheel_z, sample, rail_y, rail_z, **kwargs)
    patch = _contact_on_span(
        wheel_y, wheel_z, sample, rail_y, rail_z,
        patch_half_width_m=0.0005, patch_slices=9, **kwargs
    )
    assert point is not None and patch is not None
    assert point.penetration_m == pytest.approx(0.0013, rel=1e-6)
    assert patch.penetration_m > 0.0
    assert patch.penetration_m < point.penetration_m
    assert patch.penetration_m > 0.0005


def test_patch_reports_zero_when_the_whole_patch_is_out_of_contact():
    y = np.linspace(-0.004, 0.004, 81)
    wheel_y = y.copy()
    wheel_z = np.full_like(y, 0.002)
    rail_y = y.copy()
    rail_z = np.zeros_like(y)
    result = _contact_on_span(
        wheel_y, wheel_z, _sample(y, np.zeros_like(y)), rail_y, rail_z,
        wheel_y_m=0.0, wheel_z_m=0.0, rail_y_m=0.0,
        lower=-0.004, upper=0.004,
        patch_half_width_m=0.0005, patch_slices=9,
    )
    assert result is not None
    assert result.penetration_m == 0.0
