"""The contact damping cap must be inert when unset and binding when set."""

from __future__ import annotations

import pytest

from velch import contact
from velch.contact import ContactParameters

BASE = {
    "normal_model": "hertz_effective_radius",
    "damping_model": "delta_half_velocity",
    "tangential_model": "sditt_cubic_saturation",
    "effective_modulus_pa": 1.1393e11,
    "effective_radius_m": 0.540674,
    "normal_damping_n_s_m_1p5": 3.0e7,
    "friction_coefficient": 0.4,
    "creep_stiffness_x_n": 1.0e6,
    "creep_stiffness_lateral_n": 5.0e5,
    "reference_speed_floor_m_s": 0.1,
}


def geometry() -> contact.ContactGeometry:
    return contact.ContactGeometry(
        y_m=0.7528,
        wheel_z_m=-3.0e-4,
        rail_z_m=-2.4e-4,
        penetration_m=6.5e-5,
        normal_y=0.0,
        normal_z=1.0,
        tangent_y=1.0,
        tangent_z=0.0,
        lever_y_m=0.7528,
        lever_z_m=-0.4298,
        rail_dz_ds=0.0,
        edge_limited=False,
        stiffness_n_m_1p5=1.13e11,
        radius_star_m=0.55,
        half_width_m=0.008,
    )


def evaluate(law: ContactParameters) -> contact.ContactResponse:
    return contact.evaluate_contact(
        geometry(),
        law,
        wheel_v_y_m_s=0.0,
        wheel_v_z_m_s=-1.0,
        wheel_roll_rate_rad_s=0.0,
        wheel_spin_rate_rad_s=0.0,
        rail_v_y_m_s=0.0,
        rail_v_z_m_s=0.0,
        travel_speed_m_s=97.2,
    )


def test_cap_unset_is_the_plain_law() -> None:
    assert ContactParameters(**BASE).damping_force_cap_ratio is None


def test_cap_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        ContactParameters(**BASE, damping_force_cap_ratio=0.0)
    with pytest.raises(ValueError):
        ContactParameters(**BASE, damping_force_cap_ratio=float("nan"))


def test_cap_limits_damping_force() -> None:
    uncapped = evaluate(ContactParameters(**BASE))
    capped = evaluate(ContactParameters(**BASE, damping_force_cap_ratio=0.5))
    assert capped.normal_damping_n < uncapped.normal_damping_n
    assert capped.normal_damping_n <= 0.5 * capped.normal_elastic_n + 1e-6
    assert capped.normal_force_n < uncapped.normal_force_n
