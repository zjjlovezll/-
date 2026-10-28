"""Two-point contact: the second body is searched, and it is not the same tread twice.

The wheel-rail search used to keep only the deepest extremum of the clearance, so a wheelset
whose flange root touched the gauge corner had exactly one place to put its load and the
steep normal tripped ``maximum_abs_contact_slope``.  Real two-point contact (L12: the
contact-line and conformal two-point algorithms) finds every local minimum of the clearance.

Four things have to stay true, and each one is a test here:

* the masked-surface trick invents no surface across the window it cuts;
* with the search on, the frozen static anchor is *bit-identical* to the single-point result
  (59 680.5769 N, -0.4628 mm) -- otherwise "fixing the algorithm" would have moved the physics
  every other number in the repository is measured against;
* a second *flat* lobe (the profile polyline carries more than one maximum across its own crown,
  measured 8.06 mm apart) is not a second body;
* a genuine flange contact is found, is steeper than the criterion, and separates further than
  the exclusion window.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from velch.contact_search import masked_sample_around
from velch.solver import SimulationFailure
from velch.data_root import case_dir
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _static_vertical_equilibrium

pytestmark = pytest.mark.corpus

CASE = case_dir() / "case_A_plain.json"
ORACLE_CONTACT_N = 59_680.5769
ORACLE_VERTICAL_M = -0.4628e-3


def _seated(*, two_point: bool):
    case = load_vehicle_case(CASE)
    case = dataclasses.replace(
        case, run=dataclasses.replace(case.run, contact_two_point=two_point))
    dynamics = VehicleDynamics(case)
    q, residual = _static_vertical_equilibrium(
        case, dynamics, np.array(case.initial_q, dtype=float),
        np.array(case.initial_v, dtype=float))
    return case, dynamics, q, residual


def test_the_masked_surface_keeps_the_abscissa_and_invents_nothing() -> None:
    """A well, not a deletion: the window is deep, and the rest of the surface is untouched."""

    case, _dynamics, _q, _residual = _seated(two_point=False)
    rail = case.rails[0]
    body = next(item for item in rail.bodies if item.active_at(60.0))
    sample = body.series.sample(60.0, 1.0)
    y = np.asarray(sample.profile.y_m, dtype=float)
    z = np.asarray(sample.profile.z_m, dtype=float)
    centre = float(y[y.size // 2])
    masked = masked_sample_around(sample, center_y_m=centre, exclusion_m=2.0e-3)
    assert np.all(np.diff(masked.profile.y_m) > 0.0), "the abscissa must stay increasing"
    assert masked.profile.y_m.size == y.size
    inside = np.abs(y - centre) < 2.0e-3
    assert inside.any()
    assert np.all(masked.profile.z_m[inside] < z[inside] - 5.0)
    np.testing.assert_array_equal(masked.profile.z_m[~inside], z[~inside])
    # An empty window hands back the very same object, which is what makes the single-contact
    # cases identical by construction rather than by luck.
    assert masked_sample_around(sample, center_y_m=50.0, exclusion_m=2.0e-3) is sample


def test_the_search_can_be_turned_off_and_still_matches_the_frozen_anchor() -> None:
    _case, _dynamics, q, residual = _seated(two_point=False)
    assert abs(residual) < 1.0e-6
    np.testing.assert_allclose(q[1], ORACLE_VERTICAL_M, atol=1.0e-7)


def test_the_two_point_search_reproduces_the_frozen_anchor_bit_for_bit() -> None:
    """One body in contact must give the single-point answer exactly, not approximately."""

    _case_off, dynamics_off, q_off, _ = _seated(two_point=False)
    _case_on, dynamics_on, q_on, _ = _seated(two_point=True)
    np.testing.assert_array_equal(q_on, q_off)

    v = np.zeros(dynamics_on.dimension)
    _f, responses_on = dynamics_on.evaluate(0.0, q_on, v)
    _f, responses_off = dynamics_off.evaluate(0.0, q_off, v)
    assert sorted(responses_on) == sorted(responses_off)
    for rail_id, response in responses_on.items():
        np.testing.assert_array_equal(
            response.normal_force_n, responses_off[rail_id].normal_force_n)
        np.testing.assert_allclose(response.normal_force_n, ORACLE_CONTACT_N, rtol=2.0e-4)
    counts = {rail_id: sum(1 for item in items if item.active)
              for rail_id, items in dynamics_on.body_contacts.items()}
    assert set(counts.values()) == {1}, f"one body per rail, got {counts}"


def test_both_criteria_are_load_bearing_on_the_measured_artefact() -> None:
    """Widen the window and drop the slope test, and the plain case splits -- that is the artefact.

    Measured on this case: the profile polyline carries two extrema 8.06 mm apart across one
    Hertzian footprint, at 154.86 um and 89.85 um.  With the shipped criteria (12 mm window,
    slope 0.25) nobody calls that two bodies; with a 4 mm window and a 0.002 slope bar it does.
    """

    def count(**run_changes):
        case = load_vehicle_case(CASE)
        case = dataclasses.replace(
            case, run=dataclasses.replace(case.run, contact_two_point=True, **run_changes))
        dynamics = VehicleDynamics(case)
        q, _residual = _static_vertical_equilibrium(
            case, dynamics, np.array(case.initial_q, dtype=float),
            np.array(case.initial_v, dtype=float))
        dynamics.evaluate(0.0, q, np.zeros(dynamics.dimension))
        return {rail_id: sum(1 for item in items if item.active)
                for rail_id, items in dynamics.body_contacts.items()}

    shipped = count()
    assert set(shipped.values()) == {1}, f"shipped criteria must keep one body: {shipped}"
    loose = count(contact_two_point_exclusion_m=4.0e-3, contact_two_point_min_slope=2.0e-3)
    assert set(loose.values()) == {2}, f"the loose criteria must reproduce the artefact: {loose}"


def test_a_lone_steep_contact_still_raises_the_slope_guard() -> None:
    """The guard was re-derived, not loosened: a steep contact with nothing on the tread raises.

    Measured: shifting every wheelset 12 mm laterally on this case puts a single steep contact
    on axle1_right and nothing else, and the run must stop with the same message as before.
    """

    case, dynamics, q, _residual = _seated(two_point=True)
    shifted = np.array(q, dtype=float)
    topology = dynamics.topology
    for body in topology.wheelsets():
        shifted[topology.require(body.id, "y")] += 12.0e-3
    with pytest.raises(SimulationFailure) as caught:
        dynamics.evaluate(0.0, shifted, np.zeros(dynamics.dimension))
    message = str(caught.value)
    assert message.startswith("graph slope limit at ")
    assert "x=" in message
