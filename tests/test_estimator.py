"""Recovery behaviour of the log-space Levenberg-Marquardt estimator."""

from __future__ import annotations

import numpy as np
import pytest

from velch.inverse.estimator import (
    EstimatorError,
    Estimate,
    finite_difference_jacobian,
    gauss_newton,
)


def _linear(problem: np.ndarray, truth: np.ndarray):
    def residual(theta: np.ndarray) -> np.ndarray:
        return problem @ theta - problem @ truth
    return residual


def test_linear_system_recovered_exactly() -> None:
    problem = np.array([[1.0, 2.0], [3.0, -1.0], [0.5, 0.25]])
    truth = np.array([0.3, -0.4])
    estimate = gauss_newton(_linear(problem, truth), np.zeros(2), names=("a", "b"))
    assert np.allclose(estimate.theta, truth, atol=1e-8)
    assert estimate.cost == pytest.approx(0.0, abs=1e-16)
    assert estimate.convergence == "converged"


def test_nonlinear_waveform_recovered() -> None:
    observations = np.linspace(0.0, 1.0, 40)
    truth = np.array([0.35, -0.2])

    def model(theta: np.ndarray) -> np.ndarray:
        return np.exp(theta[0]) * np.sin(3.0 * observations) + theta[1] * observations ** 2

    target = model(truth)

    def residual(theta: np.ndarray) -> np.ndarray:
        return model(theta) - target

    estimate = gauss_newton(residual, np.zeros(2))
    assert np.allclose(estimate.theta, truth, atol=1e-6)


def test_sigma_shrinks_with_more_samples() -> None:
    rng = np.random.default_rng(3)
    truth = np.array([0.1, -0.05])
    for count in (40, 400):
        columns = rng.normal(0.0, 1.0, (count, 2))
        noise = rng.normal(0.0, 0.1, count)
        estimate = gauss_newton(lambda theta: columns @ (theta - truth) + noise,
                                np.zeros(2), noise_sigma=0.1)
        sigma = estimate.sigma
        assert np.all(sigma < 0.2)
    assert estimate.theta.size == 2


def test_singular_direction_keeps_step_bounded() -> None:
    def residual(theta: np.ndarray) -> np.ndarray:
        return np.array([2.0 * (theta[0] + theta[1]), 0.0])

    estimate = gauss_newton(residual, np.array([0.0, 0.0]))
    assert np.all(np.isfinite(estimate.theta))
    assert estimate.convergence in {"converged", "stopped after 1 steps", "no steps taken"}


def test_damping_rejects_worse_steps() -> None:
    calls = {"n": 0}

    def residual(theta: np.ndarray) -> np.ndarray:
        calls["n"] += 1
        return np.array([theta[0] ** 2 + 1.0])

    estimate = gauss_newton(residual, np.array([0.0]), max_iterations=4)
    assert estimate.cost >= 0.5
    assert calls["n"] > 0
    assert all(not item.accepted or item.cost <= estimate.cost + 1e-12
               for item in estimate.iterations)


def test_report_and_summary_are_consistent() -> None:
    estimate = gauss_newton(lambda theta: np.array([theta[0] - 0.25]), np.zeros(1),
                            names=("k",), noise_sigma=1.0)
    report = estimate.report()
    assert set(report) == {"parameters", "cost", "convergence", "steps"}
    assert report["parameters"]["k"]["scale"] == pytest.approx(float(np.exp(estimate.theta[0])))
    assert "k" in estimate.summary()
    assert isinstance(estimate, Estimate)


def test_scale_is_multiplicative() -> None:
    estimate = gauss_newton(lambda theta: np.array([theta[0] - np.log(1.15)]), np.zeros(1))
    assert estimate.scale[0] == pytest.approx(1.15, rel=1e-6)


def test_jacobian_matches_analytic() -> None:
    def residual(theta: np.ndarray) -> np.ndarray:
        return np.array([np.exp(theta[0]), np.sin(theta[1]), theta[0] * theta[1]])

    theta = np.array([0.2, -0.3])
    numeric = finite_difference_jacobian(residual, theta, step=1e-6)
    analytic = np.array([[np.exp(theta[0]), 0.0],
                         [0.0, np.cos(theta[1])],
                         [theta[1], theta[0]]])
    assert np.allclose(numeric, analytic, atol=1e-6)


def test_bad_inputs_rejected() -> None:
    with pytest.raises(EstimatorError):
        gauss_newton(lambda theta: np.array([1.0]), np.zeros(0))
    with pytest.raises(EstimatorError):
        gauss_newton(lambda theta: np.array([np.nan]), np.zeros(1))
    with pytest.raises(EstimatorError):
        gauss_newton(lambda theta: np.array([1.0]), np.zeros(1), fd_step=0.9)
    with pytest.raises(EstimatorError):
        gauss_newton(lambda theta: np.array([1.0]), np.zeros(1), max_iterations=0)
    with pytest.raises(EstimatorError):
        gauss_newton(lambda theta: np.zeros(0), np.zeros(1))
