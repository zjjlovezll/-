"""Identifiability before estimation.

A parameter can be wrong in the model and still be invisible in a given measurement:
the run may not excite it (a fastening gap that never opens at 350 km/h) or the
observation may not see it (no lateral sensor, so no lateral stiffness). Least squares
will happily return a number for either case, with a confidence interval that is pure
invention. So the question this module answers is *asked first*:

    given these channels and this operating condition, which parameters does the
    data actually separate, and by how much?

It answers with the SVD of the Jacobian, because that is the coordinate-free version
of the question. ``coverage`` distinguishes the two failures: a parameter with no
column energy is unobservable in this observation; a parameter whose direction is
buried in an ill-conditioned subspace is observable in principle but not separable
here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np


class IdentifiabilityError(ValueError):
    """The sensitivity study cannot be interpreted as asked."""


@dataclass(frozen=True)
class Sensitivity:
    """Sensitivity of one residual vector to each parameter, at one linearisation point."""

    names: tuple[str, ...]
    jacobian: np.ndarray      # (n_residuals, n_parameters), d(residual)/d(theta)
    scales: tuple[float, ...]  # residual scale per row used for normalisation
    observable: str = "unspecified"  # e.g. "waveform", "peak", "band_rms"

    def __post_init__(self) -> None:
        if self.jacobian.ndim != 2:
            raise IdentifiabilityError("jacobian must be two-dimensional")
        if not isinstance(self.observable, str) or not self.observable.strip():
            raise IdentifiabilityError("observable must be a non-empty string")
        rows, columns = self.jacobian.shape
        if columns != len(self.names):
            raise IdentifiabilityError(
                f"{columns} jacobian columns for {len(self.names)} parameters")
        if len(self.scales) != rows:
            raise IdentifiabilityError(f"{len(self.scales)} scales for {rows} residuals")
        if not np.all(np.isfinite(self.jacobian)):
            raise IdentifiabilityError("jacobian has non-finite entries")


@dataclass(frozen=True)
class Verdict:
    """What the data can and cannot separate."""

    names: tuple[str, ...]
    singular_values: tuple[float, ...]
    condition_number: float
    rank: int
    normalised_sensitivity: dict[str, float]
    identifiable: dict[str, bool]
    coverage: dict[str, str]
    notes: tuple[str, ...] = ()
    resolution: dict[str, float] = field(default_factory=dict)
    observable: str = "unspecified"

    def summary(self) -> str:
        lines = [f"rank {self.rank}/{len(self.names)}  cond {self.condition_number:.3g}  "
                 f"observable {self.observable}"]
        for name in self.names:
            flag = "identifiable" if self.identifiable[name] else "NOT identifiable"
            lines.append(f"  {name:<22} sens {self.normalised_sensitivity[name]:8.3g}  "
                         f"{flag}  ({self.coverage[name]})")
        return "\n".join(lines)


def normalised_sensitivity(sensitivity: Sensitivity) -> np.ndarray:
    """Column norms after row scaling, i.e. "how many sigmas per unit theta".

    ``theta`` is a fractional unknown, so a column norm of 1 means "a 100 % change of
    this parameter moves the weighted residual by one residual-sigma".
    """

    weights = 1.0 / np.asarray(sensitivity.scales, dtype=float)
    return np.linalg.norm(sensitivity.jacobian * weights[:, None], axis=0)


def analyse(sensitivity: Sensitivity, *, reference_sensitivity: float = 0.0,
            min_singular_ratio: float = 1.0e-3) -> Verdict:
    """SVD verdict per parameter.

    ``reference_sensitivity`` is the magnitude that counts as "a real effect" in the
    caller's units; ``0`` means "use the largest column of this study", which only
    compares parameters against each other -- adequate to spot a dead column, not to
    claim a parameter is well determined in absolute terms.
    """

    columns = normalised_sensitivity(sensitivity)
    if columns.size == 0:
        raise IdentifiabilityError("no parameters to analyse")
    scale = float(reference_sensitivity) if reference_sensitivity > 0.0 else float(columns.max())
    if not math.isfinite(scale) or scale <= 0.0:
        raise IdentifiabilityError("sensitivity scale is zero: nothing moves the residual")

    weights = 1.0 / np.asarray(sensitivity.scales, dtype=float)
    weighted = sensitivity.jacobian * weights[:, None]
    singular = np.linalg.svd(weighted, compute_uv=False)
    largest = float(singular[0]) if singular.size else 0.0
    tolerance = max(min_singular_ratio * largest, 1e-12)
    rank = int(np.count_nonzero(singular > tolerance))
    # A matrix that is rank-deficient *by our own tolerance* has no usable condition
    # number: quoting largest/smallest there would report the rounding floor.
    if rank < len(sensitivity.names) or not singular.size or singular[-1] <= 0.0:
        condition = math.inf
    else:
        condition = float(largest / singular[-1])

    identifiable: dict[str, bool] = {}
    coverage: dict[str, str] = {}
    for index, name in enumerate(sensitivity.names):
        value = float(columns[index])
        identifiable[name] = value >= 1.0e-2 * scale
        if value == 0.0:
            coverage[name] = "no column energy: observation cannot see it"
        elif not identifiable[name]:
            coverage[name] = "column energy far below the others: not separable here"
        else:
            coverage[name] = "observed"

    notes: list[str] = []
    if rank < len(sensitivity.names):
        notes.append(f"jensen rank {rank} < {len(sensitivity.names)}: parameters trade off "
                     "along the null space, do not estimate them independently")
    if condition > 1.0e6:
        notes.append(f"condition number {condition:.3g}: the normal equations will be "
                     "dominated by rounding, keep a prior or drop a parameter")

    # How far theta must move to shift the weighted residual by one sigma. This is the
    # number that says whether a parameter is usable in an inversion: a scalar peak force
    # can pass the identifiability test yet still resolve theta only to +-100 %.
    resolution = {
        name: (1.0 / float(columns[i]) if columns[i] > 0.0 else math.inf)
        for i, name in enumerate(sensitivity.names)
    }
    coarse = [f"{name} (+-{100 * resolution[name]:.3g} %)"
              for name in sensitivity.names
              if math.isfinite(resolution[name]) and resolution[name] > 0.1]
    if coarse:
        notes.append("poorly resolved: " + ", ".join(coarse) +
                     " per one-sigma residual; prefer a waveform/band observable over a "
                     "single-point extremum")
    if sensitivity.observable.strip().lower() in {"peak", "max", "maximum", "scalar"}:
        notes.append("observable is a single-point extremum: peak force is a symptom, not a "
                     "parameter fingerprint -- use the whole waveform")

    return Verdict(names=sensitivity.names,
                   singular_values=tuple(float(value) for value in singular),
                   condition_number=condition, rank=rank,
                   normalised_sensitivity={name: float(columns[i])
                                           for i, name in enumerate(sensitivity.names)},
                   identifiable=identifiable, coverage=coverage,
                   notes=tuple(notes), resolution=resolution,
                   observable=sensitivity.observable)


def finite_difference_jacobian(residual, theta: Sequence[float], steps: Sequence[float],
                               scales: Sequence[float] | None = None) -> Sensitivity:
    """Central-difference Jacobian of ``residual(theta) -> ndarray``.

    Central differences because a contact law is only piecewise smooth: one-sided
    differences bias every parameter the geometry switches on and off.
    """

    theta = np.asarray(theta, dtype=float)
    steps = np.asarray(steps, dtype=float)
    if theta.shape != steps.shape:
        raise IdentifiabilityError("theta and step vectors must have the same length")
    if np.any(steps <= 0.0):
        raise IdentifiabilityError("finite-difference steps must be positive")
    base = np.asarray(residual(theta), dtype=float)
    if base.ndim != 1:
        raise IdentifiabilityError("residual must be one-dimensional")
    columns: list[np.ndarray] = []
    for index in range(theta.size):
        forward = theta.copy()
        backward = theta.copy()
        forward[index] += steps[index]
        backward[index] -= steps[index]
        columns.append((np.asarray(residual(forward)) - np.asarray(residual(backward)))
                       / (2.0 * steps[index]))
    jacobian = np.column_stack(columns)
    scale = (np.asarray(scales, dtype=float) if scales is not None
             else np.maximum(np.abs(base), 1e-12))
    if scale.shape != (base.size,):
        raise IdentifiabilityError("scales must match the residual length")
    return Sensitivity(names=tuple(f"theta[{i}]" for i in range(theta.size)),
                       jacobian=jacobian, scales=tuple(float(v) for v in scale))
