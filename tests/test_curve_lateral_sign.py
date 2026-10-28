"""The fictitious curving force has a sign, and it is a geometric fact, not a preference.

On a station-table curve the line is ``y = s^2 / (2R)``: it turns towards +y, so the centre of
curvature sits at +y and the inertia force on the vehicle points towards -y.  The force route
(straight rails, equivalent-straight body force) was built with the opposite convention --
"outward is +y" -- which is a convention, not geometry.  ``RunSettings.curve_lateral_sign``
selects between them, defaults to the value every existing case was measured with, and is
multiplied into both the right-hand side and the action-reaction ledger so the gate cannot
disagree with the force.

Measured consequence of the two signs on R = 1100 m at 80 km/h, 0.34 s, all else equal:
``+1`` gives a net lateral force of -78.1 % of ``m v^2/R`` (pointing away from what the curve
needs); ``-1`` gives +69.1 %.  These tests pin the arithmetic that makes that difference
available at all.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from velch.data_root import case_dir
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics

pytestmark = pytest.mark.corpus

CASE = case_dir() / "case_A_final_law.json"
RADIUS_M = 1100.0


def _total_lateral(*, sign: float) -> float:
    case = load_vehicle_case(CASE)
    case = dataclasses.replace(
        case, run=dataclasses.replace(case.run, curve_radius_m=RADIUS_M,
                                      curve_lateral_sign=float(sign)))
    dynamics = VehicleDynamics(case)
    force, _contacts = dynamics.evaluate(
        0.0, np.array(case.initial_q, dtype=float), np.array(case.initial_v, dtype=float))
    rows = [dynamics.topology.require(body.id, "y")
            for body in dynamics.topology.bodies if "y" in body.dof]
    return float(sum(float(force[row]) for row in rows))


def test_the_sign_flips_exactly_twice_the_curving_force() -> None:
    plus = _total_lateral(sign=+1.0)
    minus = _total_lateral(sign=-1.0)
    case = load_vehicle_case(CASE)
    speed = abs(float(case.vehicle.travel_speed_m_s))
    mass = sum(body.mass_kg for body in VehicleDynamics(case).topology.bodies)
    expected = 2.0 * mass * speed * speed / RADIUS_M
    np.testing.assert_allclose(plus - minus, expected, rtol=1.0e-9)


def test_the_default_is_the_value_every_existing_case_was_measured_with() -> None:
    case = load_vehicle_case(CASE)
    assert case.run.curve_lateral_sign == 1.0
    default = _total_lateral(sign=1.0)
    explicit = _total_lateral(sign=+1.0)
    np.testing.assert_array_equal(np.array([default]), np.array([explicit]))


def test_only_the_two_geometrically_meaningful_values_are_accepted() -> None:
    case = load_vehicle_case(CASE)
    with pytest.raises(ValueError):
        dataclasses.replace(case.run, curve_lateral_sign=2.0)
    for sign in (-1.0, 1.0):
        assert dataclasses.replace(case.run, curve_lateral_sign=sign).curve_lateral_sign == sign
