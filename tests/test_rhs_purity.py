"""P0-5: the implicit right-hand side must be a pure function of ``(t, state)``.

Explicit integrators evaluate the right-hand side once per step, so the contact
memory (seed, age, active body, body cache, seed misses) is a one-way recursion
along the trajectory. BDF/Radau evaluate it many times at neighbouring states
*inside* one step; any memory that survives between calls turns the map into a
function of call order, and the Newton iteration then differentiates the wrong
thing.

``derivative_pure`` restores the snapshot after each call. This module pins that
down for **every** memory map the evaluator writes — including ``_body_cache``
and ``_seed_misses``, which the earlier ``validation/crh380a_m/check_purity.py``
never exercised because the production cases leave the bounded search off.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics

CASE = Path(__file__).resolve().parent.parent / "validation" / "crh380a_m" / "case_frog_N_strip05.json"


def _dynamics(bounded: bool) -> tuple[VehicleDynamics, np.ndarray, np.ndarray]:
    case = load_vehicle_case(CASE)
    if bounded:
        run = replace(case.run, contact_search_half_width_m=1.0e-3,
                      contact_seed_scope="rail_hold")
        case = replace(case, run=run)
    state = np.concatenate((np.array(case.initial_q), np.array(case.initial_v)))
    return VehicleDynamics(case), state, state.copy()


def _cross_sections(state: np.ndarray) -> list[np.ndarray]:
    """Three states: reference, pressed a little deeper, shifted sideways."""
    deeper = state.copy()
    deeper[1] -= 2.0e-4
    shifted = state.copy()
    shifted[0] += 1.0e-4
    return [state, deeper, shifted]


@pytest.mark.parametrize("bounded", [False, True], ids=["unbounded_search", "bounded_search"])
def test_derivative_pure_is_call_order_independent(bounded: bool) -> None:
    dynamics, state, _ = _dynamics(bounded)
    try:
        for section in _cross_sections(state):
            first = dynamics.derivative_pure(0.0, section)
            assert np.array_equal(first, dynamics.derivative_pure(0.0, section))
            for other in _cross_sections(state):
                dynamics.derivative_pure(0.0, other)
                again = dynamics.derivative_pure(0.0, section)
                assert np.array_equal(again, first), "a preceding evaluation changed the result"
    finally:
        dynamics.close()


@pytest.mark.parametrize("bounded", [False, True], ids=["unbounded_search", "bounded_search"])
def test_derivative_pure_undoes_memory_dirtied_by_the_raw_rhs(bounded: bool) -> None:
    """A raw ``derivative`` call must not be able to leak into a later pure call."""
    dynamics, state, _ = _dynamics(bounded)
    try:
        clean = dynamics.derivative_pure(0.0, state)
        for other in _cross_sections(state):
            dynamics.derivative(0.0, other)  # deliberately leaves the memory dirty
        assert np.array_equal(dynamics.derivative_pure(0.0, state), clean)
    finally:
        dynamics.close()


@pytest.mark.parametrize("bounded", [False, True], ids=["unbounded_search", "bounded_search"])
def test_every_memory_map_survives_a_pure_call(bounded: bool) -> None:
    dynamics, state, _ = _dynamics(bounded)
    try:
        for other in _cross_sections(state):
            dynamics.derivative(0.0, other)
        before = dynamics.snapshot_contact_state()
        dynamics.derivative_pure(0.0, state)
        after = dynamics.snapshot_contact_state()
        assert before.keys() == after.keys()
        for key in before:
            assert before[key] == after[key], f"snapshot key {key!r} was not restored"
    finally:
        dynamics.close()


def test_bounded_search_actually_writes_memory() -> None:
    """Guard against a vacuous purity test: the bounded path must write the maps."""
    dynamics, state, _ = _dynamics(True)
    try:
        dynamics.derivative(0.0, state)
        assert dynamics._contact_seed, "bounded search wrote no seed; the purity test would be vacuous"
        assert dynamics._body_cache, "no body cache was written"
        assert dynamics._seed_misses, "no seed-miss counter was written"
    finally:
        dynamics.close()


def test_snapshot_keys_cover_every_writable_map() -> None:
    dynamics, _, _ = _dynamics(False)
    try:
        keys = set(dynamics.snapshot_contact_state())
        assert keys == {"seed", "age", "active", "body", "misses"}
    finally:
        dynamics.close()


def test_rhs_sparsity_is_a_structural_superset() -> None:
    """The template must never be narrower than an exact finite-difference Jacobian."""
    from velch.vehicle_solver import _rhs_sparsity

    dynamics, state, _ = _dynamics(True)
    try:
        template = _rhs_sparsity(dynamics, state, 0.0)
        size = state.size
        dof = size // 2
        assert template.shape == (size, size)
        # q' = v is exact: the position block must be structurally zero.
        assert not template[:dof, :dof].any()
        # The probe is a finite difference of the same function the solver uses;
        # the true Jacobian must sit inside the template.
        base = dynamics.derivative_pure(0.0, state)
        step = 1e-7 * np.maximum(1.0, np.abs(state))
        dense = np.empty((size, size))
        for index in range(size):
            trial = state.copy()
            trial[index] += step[index]
            dense[:, index] = (dynamics.derivative_pure(0.0, trial) - base) / step[index]
        outside = (~template) & (np.abs(dense) > 0.0)
        scale = float(np.max(np.abs(dense)))
        worst = float(np.max(np.abs(dense[outside]))) / scale if outside.any() else 0.0
        # Sub-threshold entries are floating-point debris of the difference
        # quotient, not real coupling: the template treats anything below
        # 1e-12*max|J| as structurally zero, so they may (and do) fall outside.
        assert worst < 1e-9, f"largest outside entry is {worst:.3e} of max|J| ({int(outside.sum())} entries)"
        significant = (~template) & (np.abs(dense) > 1e-12 * scale)
        assert not significant.any(), f"{int(significant.sum())} significant entries fall outside the template"
    finally:
        dynamics.close()
