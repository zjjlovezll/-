"""Levenberg-Marquardt estimation on a parameter vector that lives in log-scale.

The inverse layer deliberately knows nothing about the dynamics: it is handed a residual
callable ``r(theta) -> ndarray`` and a starting point, and does not import the solver.  That
keeps the dependency direction ``inverse -> case`` intact and lets the same estimator drive
a synthetic recovery test, a Simpack cross-check, or a measured-campaign fit.

Everything is expressed in *log* parameters, so a reported ``theta`` is a multiplicative
correction: ``theta = ln(scale)``, ``theta = 0`` means "unchanged".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np


class EstimatorError(ValueError):
    """Raised for unusable estimator inputs."""


@dataclass(frozen=True)
class Iteration:
    """One accepted or rejected trial step."""

    index: int
    theta: np.ndarray
    cost: float
    step_norm: float
    accepted: bool
    damping: float


@dataclass(frozen=True)
class Estimate:
    """The estimate plus everything needed to judge it."""

    theta: np.ndarray
    sigma: np.ndarray
    cost: float
    residual: np.ndarray
    jacobian: np.ndarray
    covariance: np.ndarray
    iterations: tuple[Iteration, ...] = field(default_factory=tuple)
    names: tuple[str, ...] = field(default_factory=tuple)

    @property
    def scale(self) -> np.ndarray:
        """Multiplicative correction, ``exp(theta)``."""
        return np.exp(self.theta)

    @property
    def convergence(self) -> str:
        if not self.iterations:
            return "no steps taken"
        if self.iterations[-1].step_norm < 1.0e-9:
            return "converged"
        return f"stopped after {len(self.iterations)} steps"

    def report(self) -> dict[str, object]:
        """Machine-readable summary."""
        names = self.names or tuple(f"theta{i}" for i in range(self.theta.size))
        return {
            "parameters": {
                name: {
                    "log_scale": float(self.theta[i]),
                    "scale": float(np.exp(self.theta[i])),
                    "sigma_log": float(self.sigma[i]),
                    "sigma_percent": float(100.0 * self.sigma[i]),
                }
                for i, name in enumerate(names)
            },
            "cost": float(self.cost),
            "convergence": self.convergence,
            "steps": len(self.iterations),
        }

    def summary(self) -> str:
        names = self.names or tuple(f"theta{i}" for i in range(self.theta.size))
        lines = [f"estimation over {self.theta.size} parameter(s)", f"  cost {self.cost:.6g}",
                 f"  {self.convergence} in {len(self.iterations)} step(s)"]
        for i, name in enumerate(names):
            lines.append(f"  {name:<16} scale {np.exp(self.theta[i]):.6g} "
                         f"+- {100.0 * self.sigma[i]:.4g} %")
        return "\n".join(lines)


def _check_vector(values: Sequence[float], label: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size == 0:
        raise EstimatorError(f"{label} must be a non-empty 1-D sequence")
    if not np.all(np.isfinite(array)):
        raise EstimatorError(f"{label} must be finite")
    return array


def finite_difference_jacobian(residual: Callable[[np.ndarray], np.ndarray],
                               theta: np.ndarray, *, step: float = 1.0e-3) -> np.ndarray:
    """Central differences in log space; ``step`` is the log half-width."""
    if not (0.0 < step < 0.5):
        raise EstimatorError(f"finite-difference step must be in (0, 0.5), got {step}")
    base = np.asarray(residual(theta), dtype=float)
    columns = np.empty((base.size, theta.size), dtype=float)
    for i in range(theta.size):
        forward = theta.copy()
        backward = theta.copy()
        forward[i] += step
        backward[i] -= step
        columns[:, i] = (np.asarray(residual(forward), dtype=float)
                         - np.asarray(residual(backward), dtype=float)) / (2.0 * step)
    if not np.all(np.isfinite(columns)):
        raise EstimatorError("finite-difference Jacobian is not finite")
    return columns


def gauss_newton(residual: Callable[[np.ndarray], np.ndarray], theta0: Sequence[float], *,
                 names: Sequence[str] = (), noise_sigma: float | np.ndarray | None = None,
                 fd_step: float = 1.0e-3, max_iterations: int = 60,
                 initial_damping: float = 1.0e-3, damping_floor: float = 1.0e-12,
                 max_step_norm: float = 0.5, tolerance: float = 1.0e-9) -> Estimate:
    """Minimise ``0.5 * ||r(theta)||^2`` with Levenberg-Marquardt damping.

    ``max_step_norm`` bounds a single log-parameter step (0.5 means at most a factor
    ``exp(0.5) = 1.65``).  The damping is adapted per step: increase on a rejected trial,
    decrease on an accepted one.
    """
    theta = _check_vector(theta0, "theta0")
    if max_iterations < 1:
        raise EstimatorError("max_iterations must be positive")
    if not (initial_damping > 0.0):
        raise EstimatorError("initial_damping must be positive")

    current = np.asarray(residual(theta), dtype=float)
    if current.size == 0:
        raise EstimatorError("residual must return at least one value")
    if not np.all(np.isfinite(current)):
        raise EstimatorError("residual at theta0 is not finite")
    cost = float(0.5 * current @ current)
    damping = float(initial_damping)
    history: list[Iteration] = []

    for index in range(max_iterations):
        jacobian = finite_difference_jacobian(residual, theta, step=fd_step)
        normal = jacobian.T @ jacobian
        gradient = jacobian.T @ current
        diagonal = np.maximum(np.diag(normal), 1.0e-30)
        step = None
        accepted = False
        trial_cost = cost
        for _ in range(12):
            system = normal + damping * np.diag(diagonal)
            try:
                proposal = -np.linalg.solve(system, gradient)
            except np.linalg.LinAlgError:
                proposal = -np.linalg.lstsq(system, gradient, rcond=None)[0]
            norm = float(np.linalg.norm(proposal))
            if norm > max_step_norm:
                proposal *= max_step_norm / norm
                norm = max_step_norm
            candidate = theta + proposal
            candidate_residual = np.asarray(residual(candidate), dtype=float)
            if np.all(np.isfinite(candidate_residual)):
                trial_cost = float(0.5 * candidate_residual @ candidate_residual)
                if trial_cost < cost:
                    step = proposal
                    accepted = True
                    break
            damping = max(damping * 10.0, damping_floor)
        if not accepted or step is None:
            history.append(Iteration(index, theta.copy(), cost, 0.0, False, damping))
            break
        theta = theta + step
        current = np.asarray(residual(theta), dtype=float)
        previous = cost
        cost = trial_cost
        damping = max(damping / 3.0, damping_floor)
        step_norm = float(np.linalg.norm(step))
        history.append(Iteration(index, theta.copy(), cost, step_norm, True, damping))
        if step_norm <= tolerance or abs(previous - cost) <= 1.0e-15 * max(1.0, previous):
            break

    jacobian = finite_difference_jacobian(residual, theta, step=fd_step)
    normal = jacobian.T @ jacobian
    if noise_sigma is None:
        dof = max(current.size - theta.size, 1)
        variance = 2.0 * cost / dof
    else:
        sigma_array = np.asarray(noise_sigma, dtype=float)
        if sigma_array.ndim == 0:
            if not (sigma_array > 0.0):
                raise EstimatorError("noise_sigma must be positive")
            variance = float(sigma_array) ** 2
        else:
            if sigma_array.shape != current.shape:
                raise EstimatorError("per-sample noise_sigma must match the residual size")
            if not np.all(sigma_array > 0.0):
                raise EstimatorError("per-sample noise_sigma must be positive")
            variance = float(np.mean(sigma_array ** 2))
    try:
        covariance = variance * np.linalg.inv(normal)
    except np.linalg.LinAlgError:
        covariance = variance * np.linalg.pinv(normal)
    sigma = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    return Estimate(theta=theta, sigma=sigma, cost=cost, residual=current,
                    jacobian=jacobian, covariance=covariance,
                    iterations=tuple(history), names=tuple(names))
