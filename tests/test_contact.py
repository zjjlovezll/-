import math

import numpy as np

from velch.contact import (ContactGeometry, ContactParameters, evaluate_contact,
                           saturate_creep_force)


LAW = ContactParameters(
    normal_model="hertz_effective_radius", damping_model="delta_half_velocity",
    tangential_model="sditt_cubic_saturation",
    effective_modulus_pa=1e11, effective_radius_m=0.02,
    normal_damping_n_s_m_1p5=0.0, friction_coefficient=0.3,
    creep_stiffness_x_n=1e6, creep_stiffness_lateral_n=5e5,
    reference_speed_floor_m_s=0.1,
)


def geometry(depth: float) -> ContactGeometry:
    return ContactGeometry(0.0, -0.46, 0.0, depth, 0.0, 1.0, 1.0, 0.0,
                           0.0, -0.46, 0.0)


def response(depth: float, slip_x: float):
    return evaluate_contact(geometry(depth), LAW,
                            wheel_v_y_m_s=0.0, wheel_v_z_m_s=0.0,
                            wheel_roll_rate_rad_s=0.0,
                            wheel_spin_rate_rad_s=(slip_x - 2.0) / -0.46,
                            rail_v_y_m_s=0.0, rail_v_z_m_s=0.0,
                            travel_speed_m_s=2.0)


def test_no_contact_is_exactly_zero_and_zero_creep_is_finite():
    open_contact = response(0.0, 0.0)
    assert not open_contact.active
    assert open_contact.normal_force_n == 0.0
    assert open_contact.longitudinal_force_n == 0.0
    rolling = response(1e-4, 0.0)
    assert rolling.active and rolling.normal_force_n > 0
    assert rolling.longitudinal_force_n == 0.0
    assert math.isfinite(rolling.wheel_force_z_n)
    assert math.isclose(rolling.normal_force_n,
                        LAW.normal_stiffness_n_m_1p5 * (1e-4) ** 1.5, rel_tol=1e-12)


def test_creep_saturation_opposes_slip_and_obeys_friction_circle():
    positive = response(1e-4, 0.2)
    negative = response(1e-4, -0.2)
    assert positive.longitudinal_force_n < 0 < negative.longitudinal_force_n
    assert math.isclose(positive.longitudinal_force_n,
                        -negative.longitudinal_force_n, rel_tol=1e-12)
    assert positive.friction_dissipation_w >= 0
    fx, fy = saturate_creep_force(-1e9, 1e9, LAW.friction_coefficient,
                                  positive.normal_force_n)
    assert np.hypot(fx, fy) <= LAW.friction_coefficient * positive.normal_force_n * (1 + 1e-12)
