"""Carry the uncertainty through an inversion instead of dropping it.

The batch estimators in this project return a point estimate.  A reviewer of a
Kalman-based paper (Xiao, Xu, Zhu and Ren, *Mechanical Systems and Signal
Processing* 209 (2024) 111097) makes the point that the useful output is not
the estimate but the estimate *with its band*: their deterministic error was
2.4-2.7 sigma of their own posterior, and that is what let them claim the
method was understood rather than lucky.

A full unscented filter updates the state recursively; the entry-level version
of the same statement is a Gaussian posterior on a batch solve, which is what
this module provides:

    y = A r + e,   e ~ N(0, R),   r ~ N(m0, P0)
    r_hat = (A^T R^-1 A + P0^-1)^-1 (A^T R^-1 y + P0^-1 m0)
    Sigma = (A^T R^-1 A + P0^-1)^-1

so ``sigma[i]`` is meaningful only where ``A`` actually carries information, and
``coverage`` answers the question a paper has to answer: how often is the truth
inside the band the method claims?

The prior is not decoration.  With one equation per band the posterior would
otherwise be a perfect fit with zero variance, which is how a two-seed
calibration can look excellent and fail on a third.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


class UncertaintyError(ValueError):
    """Raised when the inputs cannot define a posterior."""


@dataclass(frozen=True)
class Posterior:
    """Gaussian posterior of a linear inversion, in the caller's units."""

    mean: np.ndarray
    covariance: np.ndarray
    labels: tuple[str, ...]

    @property
    def sigma(self) -> np.ndarray:
        return np.sqrt(np.clip(np.diag(self.covariance), 0.0, None))

    @property
    def relative_sigma(self) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(self.mean != 0.0, self.sigma / np.abs(self.mean), np.inf)

    @property
    def correlation(self) -> np.ndarray:
        sigma = self.sigma
        scale = np.outer(sigma, sigma)
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(scale > 0.0, self.covariance / scale, 0.0)

    def intervals(self, k: float = 1.0) -> np.ndarray:
        """``k``-sigma bounds, shape (n, 2), rows ``[mean - k sigma, mean + k sigma]``."""
        if not math.isfinite(k) or k <= 0.0:
            raise UncertaintyError("k must be finite and positive")
        return np.column_stack((self.mean - k * self.sigma, self.mean + k * self.sigma))

    def z_scores(self, truth: np.ndarray) -> np.ndarray:
        """How many sigma the truth sits away from the posterior mean."""
        truth = _vector(truth, "truth")
        _require_same_length(truth, self.mean, "truth")
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(self.sigma > 0.0, (truth - self.mean) / self.sigma, np.inf)


def _vector(values, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float).ravel()
    if array.size == 0:
        raise UncertaintyError(f"{name} is empty")
    if not np.all(np.isfinite(array)):
        raise UncertaintyError(f"{name} has non-finite entries")
    return array


def _require_same_length(left: np.ndarray, right: np.ndarray, name: str) -> None:
    if left.shape != right.shape:
        raise UncertaintyError(f"{name} needs {right.shape[0]} entries, got {left.shape[0]}")


def _as_operator(operator, n_probe: int) -> np.ndarray:
    matrix = np.atleast_2d(np.asarray(operator, dtype=float))
    if matrix.shape[1] != n_probe:
        if matrix.shape[0] == n_probe:
            matrix = matrix.T
        else:
            raise UncertaintyError(
                f"operator is {matrix.shape} and cannot act on {n_probe} unknowns"
            )
    if not np.all(np.isfinite(matrix)):
        raise UncertaintyError("operator has non-finite entries")
    return matrix


def weighted_least_squares(
    operator,
    measured,
    *,
    measurement_sigma,
    prior_sigma,
    prior_mean=None,
    labels: tuple[str, ...] | None = None,
) -> Posterior:
    """Gaussian posterior for ``measured = A @ unknowns + noise``.

    ``operator`` may be given as ``(n_response, n_probe)`` or transposed; the
    shape is inferred from the lengths of ``measured`` and ``prior_sigma``, so a
    matrix stored row-per-excitation still works (that orientation has bitten
    this project twice already).
    """
    measured = _vector(measured, "measured")
    prior = _vector(prior_sigma, "prior_sigma")
    if np.any(prior <= 0.0):
        raise UncertaintyError("prior_sigma must be strictly positive")
    matrix = _as_operator(operator, prior.size)
    if matrix.shape[0] != measured.size:
        raise UncertaintyError(
            f"operator has {matrix.shape[0]} responses but measured has {measured.size}"
        )
    sigma_y = _vector(np.broadcast_to(np.asarray(measurement_sigma, dtype=float), measured.shape),
                      "measurement_sigma")
    if np.any(sigma_y <= 0.0):
        raise UncertaintyError("measurement_sigma must be strictly positive")
    centre = np.zeros_like(prior) if prior_mean is None else _vector(prior_mean, "prior_mean")
    _require_same_length(centre, prior, "prior_mean")

    weights = 1.0 / np.square(sigma_y)
    information = matrix.T @ (matrix * weights[:, None]) + np.diag(1.0 / np.square(prior))
    right = matrix.T @ (weights * measured) + centre / np.square(prior)
    try:
        covariance = np.linalg.inv(information)
    except np.linalg.LinAlgError as exc:  # pragma: no cover - defended by the prior
        raise UncertaintyError("posterior information matrix is singular") from exc
    mean = covariance @ right
    names = labels or tuple(f"band{index + 1}" for index in range(prior.size))
    if len(names) != prior.size:
        raise UncertaintyError(f"labels need {prior.size} entries, got {len(names)}")
    return Posterior(mean=mean, covariance=0.5 * (covariance + covariance.T), labels=tuple(names))


def sigma_from_floor(floor_response, gain) -> np.ndarray:
    """Measurement sigma in unknown-units, from a no-excitation band floor.

    ``floor_response`` is what the channel reads with nothing there (m/s^2);
    dividing by the gain of that band ((m/s^2)/m) turns it into metres, which is
    the quantity a band amplitude has to beat.
    """
    floor = _vector(floor_response, "floor_response")
    scale = _vector(np.broadcast_to(np.asarray(gain, dtype=float), floor.shape), "gain")
    if np.any(scale <= 0.0):
        raise UncertaintyError("gain must be strictly positive")
    return floor / scale


@dataclass(frozen=True)
class Coverage:
    """How often the truth lands inside the claimed band, per unknown."""

    inside: np.ndarray
    fraction: float
    expected: float
    worst_z: float

    def describe(self) -> str:
        return (
            f"coverage {self.fraction * 100:.1f} % (expected {self.expected * 100:.0f} %), "
            f"worst |z| = {self.worst_z:.2f}"
        )


def coverage(posterior: Posterior, truth, *, k: float = 1.0) -> Coverage:
    """Fraction of entries whose truth lies within ``k`` sigma of the mean."""
    z = np.abs(posterior.z_scores(truth))
    inside = z <= k
    # Two-sided normal interval: P(|z| <= 1) = 68.3 %, and 95.4 % at k = 2.
    expected = math.erf(k / math.sqrt(2.0))
    return Coverage(
        inside=inside,
        fraction=float(np.count_nonzero(inside)) / float(inside.size),
        expected=expected,
        worst_z=float(np.max(z[np.isfinite(z)])) if np.any(np.isfinite(z)) else float("inf"),
    )


def fold_non_negative(posterior: Posterior) -> Posterior:
    """Clamp negative means at zero and drop their variance to the other side.

    A band amplitude cannot be negative, but an unconstrained solve happily
    returns -255 um.  Clamping the mean alone would keep a sigma that belongs to
    a value that cannot exist, so the clamped entries keep their distance to zero
    as one-sided uncertainty and are reported with ``mean == 0``.
    """
    mean = np.where(posterior.mean < 0.0, 0.0, posterior.mean)
    covariance = posterior.covariance.copy()
    for index in np.flatnonzero(posterior.mean < 0.0):
        # A half-normal draw folded onto zero has variance (1 - 2/pi) * sigma^2, not
        # sigma^2.  This line used to read ``sqrt(x) ** 2``, which is the identity: the
        # clamped coordinate kept its old sigma and then reported a perfectly certain
        # zero (mean 0 with sigma unchanged), which is the opposite of the intent.
        sigma = math.sqrt(max(float(covariance[index, index]), 0.0))
        covariance[index, index] = (1.0 - 2.0 / math.pi) * sigma * sigma
    return Posterior(mean=mean, covariance=covariance, labels=posterior.labels)
