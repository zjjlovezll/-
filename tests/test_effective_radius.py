"""B048: the straight case's 20 mm effective radius is a knob, and the geometry does not need it.

`case_A_plain.json` declares ``contact.effective_radius_m = 0.02`` with
``stiffness_policy = "fixed_effective_radius"``, so ``N = C delta^1.5`` is evaluated at a
20 mm radius.  The wheel/rail pair actually fitted at the contact has a combined radius of
0.24-0.70 m (``tests``/``scripts/s95`` measure the curvatures), i.e. the shipped law is
12-27x sharper than the geometry it is meant to describe.  The consequence is not a small
offset: the same 59.68 kN then sits at **197.6 um of penetration instead of 65.47 um**, and
because ``d(delta)/dy`` scales with the curvature sum, the *lateral* response is that much
stiffer -- which is what four rounds of "the contact is pinned" were chasing.

These tests pin the three facts that make the correction safe:

1. the shipped case still reproduces the frozen static oracle exactly (nothing frozen moved);
2. with ``stiffness_policy = "local_circular"`` -- the curvatures fitted from the profiles --
   the same 59.68 kN lands at 65.47 um, i.e. the oracle *without* the 20 mm override, so the
   override is not load bearing for the vertical calibration;
3. under that honest stiffness a 1 mm lateral shift already unloads the patch by more than
   40 %, which is the registration defect stated as a number rather than as an opinion.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from velch.data_root import case_dir
from velch.vehicle import VehicleCase, load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat

pytestmark = pytest.mark.corpus  # reads the archived cases through case_dir()

ORACLE_FORCE_N = 59_680.5769
ORACLE_PENETRATION_M = 65.47e-6
SPEED_M_S = 22.2222
WHEEL_RADIUS_M = 0.43


def _seat_and_load(case: VehicleCase, shift_m: float = 0.0):
    dynamics = VehicleDynamics(case)
    velocity = np.zeros(dynamics.dimension)
    for body in dynamics.topology.bodies:
        try:
            velocity[dynamics.topology.require(body.id, "spin")] = SPEED_M_S / WHEEL_RADIUS_M
        except Exception:
            pass
    seated, residual = _seat(case, dynamics, np.zeros(dynamics.dimension), velocity)
    state = np.array(seated, dtype=float)
    if shift_m:
        for body in dynamics.topology.bodies:
            if body.id.startswith("wheelset"):
                state[dynamics.topology.require(body.id, "y")] += shift_m
    dynamics.evaluate(0.0, state, velocity)
    entry = next(e for e in dynamics.body_contacts["axle1_left"] if e.geometry is not None)
    return residual, entry


def test_the_shipped_case_now_uses_the_fitted_stiffness_and_hits_the_documented_oracle():
    """B048 applied: the 20 mm override is retired by default everywhere.

    The case still *declares* ``effective_radius_m = 0.02`` — that key is left in the archived JSON
    so the change is one line and reviewable — but ``stiffness_policy`` now defaults to
    ``local_circular``, so the declaration no longer reaches the law.  What the run owes is the pair
    this project has always quoted: 59 680.5769 N at 65.47 um, not 59 680.5769 N at 197.62 um.
    """
    case = load_vehicle_case(case_dir() / "case_A_plain.json")
    assert case.contact.stiffness_policy == "local_circular"
    residual, entry = _seat_and_load(case)
    assert residual < 1e-5
    assert entry.normal_force_n == pytest.approx(ORACLE_FORCE_N, abs=1.0)
    assert entry.geometry.penetration_m == pytest.approx(ORACLE_PENETRATION_M, rel=2e-3)
    # And the override is inert: declaring it explicitly changes nothing now.
    explicit = dataclasses.replace(
        case, contact=dataclasses.replace(case.contact, stiffness_policy="fixed_effective_radius"))
    _, overridden = _seat_and_load(explicit)
    assert overridden.geometry.penetration_m == pytest.approx(197.62e-6, rel=1e-3)
    assert overridden.geometry.penetration_m > 2.5 * entry.geometry.penetration_m


def test_the_measured_curvatures_reproduce_the_oracle_without_the_override():
    """The vertical calibration does not need the 20 mm radius."""

    base = load_vehicle_case(case_dir() / "case_A_plain.json")
    case = dataclasses.replace(
        base, contact=dataclasses.replace(base.contact, stiffness_policy="local_circular"))
    residual, entry = _seat_and_load(case)
    assert residual < 1e-5
    assert entry.normal_force_n == pytest.approx(ORACLE_FORCE_N, abs=1.0)
    assert entry.geometry.penetration_m == pytest.approx(ORACLE_PENETRATION_M, rel=2e-2)
    assert entry.geometry.radius_star_m is not None
    assert 0.3 < entry.geometry.radius_star_m < 1.0


def test_under_the_honest_stiffness_a_one_millimetre_shift_unloads_the_patch():
    base = load_vehicle_case(case_dir() / "case_A_plain.json")
    case = dataclasses.replace(
        base, contact=dataclasses.replace(base.contact, stiffness_policy="local_circular"))
    _, centred = _seat_and_load(case)
    _, shifted = _seat_and_load(case, shift_m=1.0e-3)
    ratio = shifted.normal_force_n / centred.normal_force_n
    assert ratio < 0.60, ratio
    assert shifted.geometry.lever_y_m == pytest.approx(centred.geometry.lever_y_m - 1.0e-3,
                                                       abs=1e-5)
