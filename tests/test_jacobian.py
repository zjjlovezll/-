"""Analytic Jacobian: exact on the linear part, honest about the frozen geometry.

The tight numerical gate lives in
``validation/crh380a_m/check_jacobian.py`` and in ``jacobian.frozen_geometry_error``,
because it needs a converged state from a full run. What is asserted here is what can
be asserted cheaply and structurally: the block layout, the exactness of the linear
(suspension + track) part, that the contact contribution is present with the right
sign order of magnitude, and that asking for a Jacobian never disturbs the contact
search memory the integrator depends on.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from velch.jacobian import JacobianAssembler, frozen_geometry_error
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _static_vertical_equilibrium
from velch.data_root import case_dir

CASE = case_dir() / "case_frog_N_strip05.json"


@pytest.fixture(scope="module")
def dynamics_and_state():
    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    if case.equilibrate_vertical:
        q, _residual = _static_vertical_equilibrium(case, dynamics, q, v)
    return dynamics, q, v


def test_block_layout(dynamics_and_state) -> None:
    dynamics, q, v = dynamics_and_state
    n = dynamics.dimension
    jacobian = JacobianAssembler(dynamics).full(0.0, q, v)
    assert jacobian.shape == (2 * n, 2 * n)
    # d(q')/dq = 0 and d(q')/dv = I are structural, not computed.
    assert not jacobian[:n, :n].any()
    np.testing.assert_array_equal(jacobian[:n, n:], np.eye(n))
    assert np.all(np.isfinite(jacobian))


def test_linear_part_is_exact_without_contact(dynamics_and_state) -> None:
    """Lift the wheels clear of the rail: what is left is springs and dampers only.

    Note the sign: penetration grows when a wheelset is lowered, so clearing the
    contact means raising them. 0.1 mm is already enough for this case (82 um of
    penetration at equilibrium); 1 mm leaves a comfortable margin.
    """
    dynamics, q, v = dynamics_and_state
    lifted = q.copy()
    for axle in range(4):
        lifted[5 * axle + 1] += 1.0e-3
    error = frozen_geometry_error(dynamics, 0.0, lifted, v)
    # Not exactly zero: the finite difference of a linear function still carries the
    # roundoff of the difference quotient (~1e-11 of the largest entry).
    assert error["dq"] < 1.0e-9
    assert error["dv"] < 1.0e-9

    # ... and the contact contribution really disappears, rather than being missed
    # by both sides of the comparison.
    contact_q, _contact_v = JacobianAssembler(dynamics).blocks(0.0, lifted, v)
    in_contact_q, _in_contact_v = JacobianAssembler(dynamics).blocks(0.0, q, v)
    assert np.abs(contact_q).max() > 0.0
    assert np.abs(in_contact_q).max() > np.abs(contact_q).max() * 1.05


def test_frozen_geometry_error_matches_the_recorded_approximation(dynamics_and_state) -> None:
    """A tripwire, not a tolerance: this is the measured 2026-10-21 number.

    The analytic block uses the deepest-slice stiffness while the right-hand side
    re-evaluates a strip integral, so the rail rows are ~20 % stiff. Anything far
    outside that envelope means the assembly broke, not that the model improved.
    """
    dynamics, q, v = dynamics_and_state
    error = frozen_geometry_error(dynamics, 0.0, q, v)
    assert error["dv"] < 0.10
    assert error["dq"] < 0.40


def test_asking_for_a_jacobian_does_not_disturb_contact_memory(dynamics_and_state) -> None:
    dynamics, q, v = dynamics_and_state
    assembler = JacobianAssembler(dynamics)
    dynamics.derivative(0.0, np.concatenate((q, v)))
    before = dynamics.snapshot_contact_state()
    assembler.blocks(0.0, q, v)
    after = dynamics.snapshot_contact_state()
    assert before.keys() == after.keys()
    for key in before:
        assert before[key] == after[key], key


def test_every_block_is_finite_at_a_perturbed_state(dynamics_and_state) -> None:
    dynamics, q, v = dynamics_and_state
    for scale in (1.0e-6, 1.0e-3):
        qq = q + scale
        vv = v - scale
        jacobian_q, jacobian_v = JacobianAssembler(dynamics).blocks(0.0, qq, vv)
        assert np.all(np.isfinite(jacobian_q))
        assert np.all(np.isfinite(jacobian_v))
