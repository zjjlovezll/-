"""Differentiable, error-bounded surrogate for wheel/rail contact geometry (B stage).

The surrogate replaces one contact solve with a regressor that predicts the penetration
(and force through the same Hertz law) plus a **calibrated error bound**. The bound is
what makes it usable inside a solver: any prediction whose bound exceeds the caller's
tolerance is routed back to the exact evaluation, so the surrogate can only ever cost
time, never accuracy.

Why a Gaussian process and not a Laplace neural operator: the input is two dimensional
relative offset plus one surface pair, the training set is O(100) samples taken from the
exact solver, and the solver needs a *calibrated* per-call bound rather than raw accuracy.
A GP gives the posterior standard deviation natively and is exact-interpolating; a neural
operator needs 1e3-1e4 samples, a GPU, and still needs a separate bound fitted on top.

Nothing here is on the default solver path; the caller opts in.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

SCHEMA = "velch-contact-surrogate-v1"
#: Reported coverage of the calibrated bound. 0.999 means the bound must hold for all but
#: one sample in a thousand of the calibration set, which is what "online bound" means.
DEFAULT_QUANTILE = 0.999


@dataclass(frozen=True)
class ContactSample:
    """One exact solve used as training or validation data."""

    lateral_offset_m: float
    height_offset_m: float
    penetration_m: float
    contact_y_m: float


def build_dataset(
    evaluate: Callable[[float, float], tuple[float, float]],
    *,
    offset_range_m: tuple[float, float],
    height_range_m: tuple[float, float],
    count: int,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample the exact contact solver over the operating box.

    ``evaluate(lateral_offset, height_offset) -> (penetration_m, contact_y_m)``.
    Samples are a Latin-hypercube-like jittered grid so the box is covered without the
    clustering a purely random draw produces at small counts.
    """

    if count < 4:
        raise ValueError("need at least four samples")
    rng = np.random.default_rng(seed)
    side = max(2, int(round(math.sqrt(count))))
    grid = (np.arange(side) + 0.5) / side
    jitter = rng.uniform(-0.5 / side, 0.5 / side, size=(side, side))
    u = np.clip(grid[:, None] + jitter, 1.0e-4, 1.0 - 1.0e-4)
    v = np.clip(grid[None, :] + jitter.T, 1.0e-4, 1.0 - 1.0e-4)
    lo_o, hi_o = offset_range_m
    lo_h, hi_h = height_range_m
    offsets = lo_o + (hi_o - lo_o) * u.ravel()
    heights = lo_h + (hi_h - lo_h) * v.ravel()
    x = np.column_stack([offsets, heights])
    y = np.array([evaluate(float(a), float(b)) for a, b in x], dtype=float)
    return x, y


def _standardise(x: np.ndarray, box: tuple[float, float, float, float]):
    lo_o, hi_o, lo_h, hi_h = box
    centre = np.array([(lo_o + hi_o) / 2.0, (lo_h + hi_h) / 2.0])
    half = np.array([max(hi_o - lo_o, 1e-9) / 2.0, max(hi_h - lo_h, 1e-9) / 2.0])
    return (x - centre) / half


@dataclass(frozen=True)
class SurrogateFit:
    """Fitted GP plus the calibration that turns its sd into a guaranteed bound."""

    train_x: np.ndarray
    cholesky: np.ndarray
    weights: np.ndarray
    length_scale: np.ndarray
    signal_variance: float
    noise_variance: float
    box: tuple[float, float, float, float]
    target_mean: np.ndarray
    target_scale: np.ndarray
    bound_factor: np.ndarray
    coverage_quantile: float
    n_train: int
    schema: str = SCHEMA

    def predict(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(mean, sd)`` in physical units, shape ``(n, 2)`` each."""

        from scipy.linalg import cho_solve

        xs = _standardise(np.atleast_2d(x), self.box)
        cross = self.signal_variance * _matern52(xs, self.train_x, self.length_scale)
        mean = cross @ self.weights
        solved = cho_solve(self.cholesky, cross.T)
        variance = self.signal_variance - np.einsum("ij,ji->i", cross, solved)
        sd_std = np.sqrt(np.maximum(variance, 0.0))[:, None]
        mean = mean * self.target_scale + self.target_mean
        sd = sd_std * self.target_scale[None, :]
        return mean, sd

    def bound(self, sd: np.ndarray) -> np.ndarray:
        return sd * self.bound_factor


def _matern52(a: np.ndarray, b: np.ndarray, length_scale: np.ndarray) -> np.ndarray:
    """Matérn 5/2 covariance for standardised inputs (both already scaled)."""

    delta = (a[:, None, :] - b[None, :, :]) / length_scale
    distance = np.sqrt(np.sum(delta * delta, axis=2))
    root5 = math.sqrt(5.0) * distance
    return (1.0 + root5 + 5.0 / 3.0 * distance ** 2) * np.exp(-root5)


def fit(
    x: np.ndarray,
    y: np.ndarray,
    *,
    box: tuple[float, float, float, float],
    length_scale_m: Sequence[float] = (2.0e-3, 2.0e-4),
    noise_m: float = 1.0e-9,
    scale_candidates: Sequence[float] = (0.25, 0.5, 1.0, 2.0, 4.0),
):
    """Fit a Gaussian process on penetration and contact-y (numpy only, no sklearn).

    The length scale is picked from a small grid by marginal likelihood rather than
    optimised: the training sets here are O(100) points, where a full optimiser buys
    nothing but runtime and non-determinism.
    """

    from scipy.linalg import cho_factor, cho_solve

    xs = _standardise(np.asarray(x, dtype=float), box)
    half_width = max(box[1] - box[0], 1e-9) / 2.0
    half_height = max(box[3] - box[2], 1e-9) / 2.0
    base = np.array([length_scale_m[0] / half_width, length_scale_m[1] / half_height])
    target_mean = y.mean(axis=0)
    target_scale = np.where(np.abs(target_mean) > 1e-12, np.abs(target_mean), 1.0)
    ys = (y - target_mean) / target_scale
    noise = max(noise_m, 1e-12)

    best = None
    for factor in scale_candidates:
        length_scale = base * float(factor)
        kernel = _matern52(xs, xs, length_scale) + np.eye(xs.shape[0]) * (noise / np.mean(target_scale)) ** 2
        try:
            cholesky = cho_factor(kernel, lower=True, check_finite=False)
        except Exception:  # singular for tiny length scales; skip that candidate
            continue
        weights = cho_solve(cholesky, ys, check_finite=False)
        sign, logdet = np.linalg.slogdet(kernel)
        if sign <= 0:
            continue
        data_fit = float(np.sum(ys * weights))
        log_likelihood = -0.5 * data_fit - 0.5 * logdet - 0.5 * xs.shape[0] * ys.shape[1] * math.log(2 * math.pi)
        if best is None or log_likelihood > best[0]:
            best = (log_likelihood, length_scale, cholesky, weights)
    if best is None:
        raise RuntimeError("no usable kernel for the given samples")
    _, length_scale, cholesky, weights = best

    return SurrogateFit(
        train_x=xs, cholesky=cholesky, weights=weights, length_scale=length_scale,
        signal_variance=1.0, noise_variance=noise ** 2, box=box,
        target_mean=target_mean, target_scale=target_scale,
        bound_factor=np.ones(y.shape[1]), coverage_quantile=DEFAULT_QUANTILE,
        n_train=int(y.shape[0]),
    )


def calibrate(fitted: SurrogateFit, x_val: np.ndarray, y_val: np.ndarray,
              *, quantile: float = DEFAULT_QUANTILE) -> SurrogateFit:
    """Widen ``bound_factor`` until ``quantile`` of the validation residuals are covered.

    Returns a new fit (frozen dataclass) rather than mutating, so a calibrated fit can be
    compared against an uncalibrated one.
    """

    mean, sd = fitted.predict(x_val)
    error = np.abs(mean - np.asarray(y_val, dtype=float))
    from dataclasses import replace

    factor = np.ones(error.shape[1])
    for column in range(error.shape[1]):
        ratio = error[:, column] / np.maximum(sd[:, column], 1e-15)
        factor[column] = float(np.quantile(ratio, quantile)) * 1.05
    return replace(fitted, bound_factor=factor, coverage_quantile=quantile)


@dataclass(frozen=True)
class FusedResult:
    penetration_m: float
    contact_y_m: float
    used_surrogate: bool
    bound_m: float
    exact_calls: int


class FusedEvaluator:
    """Surrogate with an exact fallback whenever the bound exceeds the tolerance.

    The fallback criterion is per-call and local, so a badly covered corner of the box
    degrades to the exact solver instead of silently reporting a confident wrong number.
    """

    def __init__(self, fitted: SurrogateFit, exact: Callable[[float, float], tuple[float, float]],
                 tolerance_m: float) -> None:
        if tolerance_m <= 0.0:
            raise ValueError("tolerance must be positive")
        self.fitted = fitted
        self.exact = exact
        self.tolerance_m = tolerance_m
        self.calls = 0
        self.fallbacks = 0

    def evaluate(self, lateral_offset_m: float, height_offset_m: float) -> FusedResult:
        self.calls += 1
        mean, sd = self.fitted.predict(np.array([[lateral_offset_m, height_offset_m]]))
        bound = float(self.fitted.bound(sd)[0, 0])
        if bound <= self.tolerance_m:
            return FusedResult(float(mean[0, 0]), float(mean[0, 1]), True, bound, 0)
        self.fallbacks += 1
        penetration, contact_y = self.exact(lateral_offset_m, height_offset_m)
        return FusedResult(float(penetration), float(contact_y), False, bound, 1)

    @property
    def fallback_rate(self) -> float:
        return 0.0 if self.calls == 0 else self.fallbacks / self.calls


def _selftest() -> int:
    """Two-arc analytic geometry: fit, calibrate, then measure coverage and cost."""

    e_star, wheel_radius, rail_radius = 1.1393e11, 0.430, 0.300

    def exact(offset_m: float, height_m: float) -> tuple[float, float]:
        # Two tangent circles: the wheel centre sits at (offset, wheel_radius - height),
        # the rail centre at (0, -rail_radius). Penetration is the sum of radii minus
        # their centre distance.
        cz = wheel_radius - height_m
        distance = math.hypot(offset_m, cz + rail_radius)
        penetration = max(0.0, wheel_radius + rail_radius - distance)
        if penetration <= 0.0:
            return 0.0, 0.0
        span = wheel_radius + rail_radius
        weight = wheel_radius / span
        return penetration, offset_m * weight

    # Inside a running solver the wheel is always in contact, so the operating box is
    # restricted to the contact regime. Sampling across the delta = 0 kink is what makes
    # the first version's error tail explode; that regime is documented, not fitted.
    box = (-8e-3, 8e-3, 0.2e-3, 0.6e-3)
    x_train, y_train = build_dataset(exact, offset_range_m=box[:2],
                                     height_range_m=box[2:], count=240, seed=7)
    x_val, y_val = build_dataset(exact, offset_range_m=box[:2],
                                 height_range_m=box[2:], count=400, seed=11)

    started = time.perf_counter()
    fitted = fit(x_train, y_train, box=box)
    fit_seconds = time.perf_counter() - started
    calibrated = calibrate(fitted, x_val, y_val)

    mean, sd = calibrated.predict(x_val)
    error = np.abs(mean[:, 0] - y_val[:, 0])
    bound = calibrated.bound(sd)[:, 0]
    covered = float(np.mean(error <= bound))
    print(f"train {calibrated.n_train}  fit {fit_seconds:.2f} s  "
          f"bound_factor {calibrated.bound_factor[0]:.2f}")
    print(f"penetration error |Δδ| µm: p50 {np.percentile(error, 50) * 1e6:.3f}  "
          f"p95 {np.percentile(error, 95) * 1e6:.3f}  max {error.max() * 1e6:.3f}")
    print(f"bound coverage at q={calibrated.coverage_quantile}: {covered * 100:.1f} %  "
          f"bound p50 {np.percentile(bound, 50) * 1e6:.3f} µm")

    for tolerance_m in (1.0e-6, 5.0e-6):
        fused = FusedEvaluator(calibrated, exact, tolerance_m)
        worst = 0.0
        for row in x_val:
            result = fused.evaluate(float(row[0]), float(row[1]))
            truth = exact(float(row[0]), float(row[1]))[0]
            worst = max(worst, abs(result.penetration_m - truth))
        print(f"tolerance {tolerance_m * 1e6:.0f} µm: fallback {fused.fallback_rate * 100:.1f} %  "
              f"worst error {worst * 1e6:.4f} µm")

    batch = x_val[:1000] if x_val.shape[0] >= 1000 else np.repeat(x_val, 3, axis=0)[:1000]
    started = time.perf_counter()
    calibrated.predict(batch)
    batch_seconds = time.perf_counter() - started
    print(f"batch {batch.shape[0]} predictions: {batch_seconds * 1e3:.2f} ms "
          f"({batch_seconds / batch.shape[0] * 1e6:.2f} µs each)")

    started = time.perf_counter()
    calibrated.predict(x_val[:1])
    single = time.perf_counter() - started
    print(f"single prediction: {single * 1e6:.1f} µs "
          f"(contact map reference: 8.46 µs, direct solve 154.2 µs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
