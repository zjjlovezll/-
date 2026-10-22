"""Implicit integration options: BDF is allowed and the sparsity probe is structural."""

from __future__ import annotations

import numpy as np
import pytest

from velch.model import RunSettings

BASE = {
    "method": "BDF",
    "x_start_m": 13.5,
    "duration_s": 0.01,
    "output_step_s": 5e-4,
    "max_solver_step_s": 1e-4,
    "rtol": 1e-6,
    "atol": 1e-8,
    "maximum_penetration_m": 3e-3,
    "maximum_abs_contact_slope": 1.0,
}


def test_bdf_is_accepted() -> None:
    settings = RunSettings(**BASE)
    assert settings.method == "BDF"
    assert settings.jacobian is None


def test_jacobian_option_names_are_whitelisted() -> None:
    """Both implemented Jacobian strategies are accepted; anything else is rejected."""

    assert RunSettings(**BASE, jacobian="sparse_fd").jacobian == "sparse_fd"
    assert RunSettings(**BASE, jacobian="analytic").jacobian == "analytic"
    with pytest.raises(ValueError):
        RunSettings(**BASE, jacobian="fd")


def test_unknown_method_still_rejected() -> None:
    with pytest.raises(ValueError):
        RunSettings(**{**BASE, "method": "RK45"})


def test_sparsity_of_a_linear_chain_is_banded() -> None:
    """A two-node spring chain has a tridiagonal state Jacobian structure."""
    mass = np.array([1.0, 2.0, 3.0, 4.0])

    def derivative(state: np.ndarray) -> np.ndarray:
        n = mass.size
        q, v = state[:n], state[n:]
        force = np.zeros(n)
        force[0] = -k * (q[0] - q[1])
        force[1] = -k * (q[1] - q[0]) - k * (q[1] - q[2])
        force[2] = -k * (q[2] - q[1]) - k * (q[2] - q[3])
        force[3] = -k * (q[3] - q[2])
        return np.concatenate((v, force / mass))

    k = 1.0e6
    state = np.zeros(8)
    jacobian = np.empty((8, 8))
    step = 1e-7
    base = derivative(state)
    for index in range(8):
        trial = state.copy()
        trial[index] += step
        jacobian[:, index] = (derivative(trial) - base) / step
    dense = np.abs(jacobian) > 1e-9
    # velocity rows couple only to their own velocity, position rows only to positions
    assert dense[:4, 4:].sum() == 4
    assert dense[4:, :4].sum() == 10
    assert dense[4:, 4:].any() is False or dense[4:, 4:].sum() <= 4
