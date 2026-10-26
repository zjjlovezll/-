"""Recover a short-wave depth *profile* from the harmonic ladder it excites.

Why this exists
---------------

Everything measured so far says the short-wave channel carries one number per run:
above the primary-suspension frequency the axle box barely moves, the spring
compression equals the rail displacement, and the response collapses to

    a_box  ~=  (2 pi f_n)^2 * A          f_n = sqrt(k_primary / m_box)

which is why a 30 um / 50 mm corrugation inverted to within 10 % from one division
and why the same constant does not transfer across speeds.  That is a *single*
observation of a *single* amplitude -- the rank-one problem that made the
0.1-2 m band matrix un-invertible.

A real short-wave defect is periodic but not sinusoidal: grinding patterns,
wheel polygons and corrugation all carry harmonics.  Because the contact is
single-sided and stiff, each harmonic order ``n`` produces its own line at
``n * f1`` in the acceleration, with its own gain and its own noise floor.  So one
run yields as many independent observations as there are detectable orders --
enough to recover the *shape* of the depth, not just its fundamental.

That is the design here: project the measured channel onto ``n * f1`` for
``n = 1..N`` (coherent least squares, the estimator S7e/S9-6 already use), learn
one complex gain per order from a calibration run of known depth, then solve for
the depth harmonics with a prior and report a covariance.

Relation to the literature
--------------------------

* The Bayesian Kalman filter of Xiao et al. (MSSP 209, 2024) contributes the thing
  this project kept missing: an explicit posterior, so a band comes back as
  ``mean +- sigma`` and is judged by coverage rather than by a point error.  It
  carries a state vector along the structure; we carry a harmonic vector along
  one defect, which is the same algebra on a much smaller state.
* The dual filter of Han et al. (Eng. Struct. 365, 2026) uses harmonics at
  ``n * f_sleeper`` to update *stiffness*.  Here the harmonics come from the
  defect's own period and update the *depth profile*.  That inverts their
  dependency: we do not need the vehicle to be driven by periodic sleeper
  excitation, which our model has never been shown to produce.

The gain per order is measured with the +/- differential (two runs, geometry
cancels exactly), so no statistical cancellation and no assumption of additivity
across bands is needed -- the same order is excited in both runs.

What it cannot do
-----------------

* It assumes the defect is periodic with a known period.  For a non-periodic
  patch the harmonic ladder collapses to a single wide line and this reduces to
  the single-constant estimator, with its 10-25 % bias.
* Orders above the output band (or where the gain drops into the floor) carry no
  information: their posterior stays at the prior, which is reported honestly
  rather than as a recovered zero.
* Contact loss bounds the linear range: at 60 um peak-to-peak against a 65.8 um
  static penetration the contact opens once per revolution and the per-order
  gains stop being constants (measured 146 % spread across 15/30/60 um).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..uncertainty import Posterior, weighted_least_squares

__all__ = [
    "HarmonicModel",
    "HarmonicInversion",
    "DepthProfile",
    "harmonic_amplitudes",
    "calibrate_gains",
    "invert_corrugation",
    "coverage_across_orders",
]


class HarmonicError(ValueError):
    """A harmonic-ladder request that cannot be answered as asked."""


def _orders(orders) -> tuple[int, ...]:
    clean = tuple(sorted({int(order) for order in orders}))
    if not clean:
        raise HarmonicError("need at least one harmonic order")
    if clean[0] < 1:
        raise HarmonicError(f"harmonic orders are 1-based; got {clean[0]}")
    return clean


def harmonic_amplitudes(time_s, signal, fundamental_hz: float,
                        orders) -> dict[int, complex]:
    """Project ``signal`` onto ``n * fundamental_hz`` and return complex amplitudes.

    A complex amplitude here means ``A cos(2 pi n f t) + B sin(2 pi n f t)`` with
    ``A - iB``, the same convention the long-wave estimator uses, so a phase can be
    carried through the calibration and cancelled in the inversion.
    """

    t = np.asarray(time_s, dtype=float)
    y = np.asarray(signal, dtype=float)
    if t.shape != y.shape or t.size < 4:
        raise HarmonicError("time and signal must be equal-length arrays of at least four samples")
    if not math.isfinite(fundamental_hz) or fundamental_hz <= 0.0:
        raise HarmonicError(f"fundamental frequency must be positive; got {fundamental_hz!r}")
    span = float(t[-1] - t[0])
    if span <= 0.0:
        raise HarmonicError("time must increase")
    amplitudes: dict[int, complex] = {}
    for order in _orders(orders):
        frequency = order * fundamental_hz
        if frequency * 2.0 > 1.0 / float(np.median(np.diff(t))):
            raise HarmonicError(
                f"order {order} sits at {frequency:.1f} Hz, above the record's Nyquist; "
                f"drop the order or raise the sampling rate")
        design = np.column_stack([np.cos(2.0 * math.pi * frequency * t),
                                  np.sin(2.0 * math.pi * frequency * t)])
        (a, b), *_ = np.linalg.lstsq(design, y, rcond=None)
        amplitudes[order] = complex(a, -b)
    return amplitudes


@dataclass(frozen=True)
class HarmonicModel:
    """Measured complex gain per harmonic order: response per metre of depth."""

    gains: dict[int, complex]
    reference_depth_m: float
    name: str = ""

    def __post_init__(self) -> None:
        if not self.gains:
            raise HarmonicError("a harmonic model needs at least one order")
        if not math.isfinite(self.reference_depth_m) or self.reference_depth_m <= 0.0:
            raise HarmonicError(
                f"reference depth must be positive; got {self.reference_depth_m!r}")
        for order, gain in self.gains.items():
            if int(order) < 1:
                raise HarmonicError(f"harmonic order must be 1-based; got {order!r}")
            if not (math.isfinite(gain.real) and math.isfinite(gain.imag)):
                raise HarmonicError(f"gain for order {order} is not finite")

    @property
    def orders(self) -> tuple[int, ...]:
        return tuple(sorted(self.gains))

    def predict(self, depth: dict[int, complex]) -> dict[int, complex]:
        return {order: self.gains[order] * depth.get(order, 0.0 + 0.0j)
                for order in self.orders}

    def silent_orders(self, floor: float) -> tuple[int, ...]:
        """Orders whose gain is below ``floor``: they observe nothing about depth."""

        return tuple(order for order in self.orders if abs(self.gains[order]) < floor)


def calibrate_gains(period_m: float, depth_m: float, speed_m_s: float,
                    time_s, signal) -> HarmonicModel:
    """Learn the per-order gains from a run whose corrugation is known."""

    if period_m <= 0.0 or speed_m_s <= 0.0:
        raise HarmonicError("period and speed must be positive")
    if depth_m <= 0.0:
        raise HarmonicError("depth must be positive")
    fundamental = speed_m_s / period_m
    max_order = int(math.floor(0.45 / (fundamental * float(np.median(np.diff(time_s))))))
    if max_order < 1:
        raise HarmonicError(
            f"a {period_m:g} m period at {speed_m_s:g} m/s is {fundamental:.1f} Hz; the record "
            f"cannot see even its first harmonic")
    orders = tuple(range(1, max_order + 1))
    amplitudes = harmonic_amplitudes(time_s, signal, fundamental, orders)
    gains = {order: amplitudes[order] / depth_m for order in orders}
    return HarmonicModel(gains=gains, reference_depth_m=depth_m,
                         name=f"calibrated at {depth_m * 1e6:.1f} um, "
                              f"{period_m * 1e3:.0f} mm, {speed_m_s * 3.6:.0f} km/h")


@dataclass(frozen=True)
class DepthProfile:
    """Depth as a function of mileage, from real and imaginary harmonic coefficients."""

    period_m: float
    coefficients: dict[int, complex]
    phase_origin_m: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.period_m) or self.period_m <= 0.0:
            raise HarmonicError("period must be positive")
        for order, value in self.coefficients.items():
            if int(order) < 1:
                raise HarmonicError(f"harmonic order must be 1-based; got {order!r}")

    def at(self, s_m) -> np.ndarray:
        """Depth in metres at one mileage or an array of them."""

        s = np.asarray(s_m, dtype=float)
        total = np.zeros_like(s)
        for order, value in self.coefficients.items():
            angle = 2.0 * math.pi * order * (s - self.phase_origin_m) / self.period_m
            total += (value.real * np.cos(angle) - value.imag * np.sin(angle))
        return total

    @property
    def peak_to_peak_m(self) -> float:
        if not self.coefficients:
            return 0.0
        span = np.linspace(0.0, self.period_m, 721)
        profile = self.at(span)
        return float(profile.max() - profile.min())


@dataclass(frozen=True)
class HarmonicInversion:
    """Posterior over the depth harmonics, plus the profile it implies."""

    model: HarmonicModel
    posterior: Posterior
    orders: tuple[int, ...]
    fundamental_hz: float
    period_m: float
    measured: dict[int, complex] = field(default_factory=dict, repr=False)

    def depth(self) -> DepthProfile:
        coefficients = {}
        for position, order in enumerate(self.orders):
            coefficients[order] = complex(float(self.posterior.mean[2 * position]),
                                          float(self.posterior.mean[2 * position + 1]))
        return DepthProfile(period_m=self.period_m, coefficients=coefficients)

    def amplitude_sigma(self) -> dict[int, float]:
        """One sigma on each order's depth amplitude (magnitude, not per component)."""

        out = {}
        for position, order in enumerate(self.orders):
            var_re = float(self.posterior.covariance[2 * position, 2 * position])
            var_im = float(self.posterior.covariance[2 * position + 1, 2 * position + 1])
            out[order] = math.sqrt(max(var_re, 0.0) + max(var_im, 0.0))
        return out

    def peak_to_peak_m(self) -> float:
        return self.depth().peak_to_peak_m


def invert_corrugation(model: HarmonicModel, measured: dict[int, complex], *,
                       measurement_sigma: float,
                       prior_sigma: float,
                       fundamental_hz: float,
                       period_m: float,
                       prior_mean: float = 0.0,
                       floor_gain: float = 0.0,
                       labels: tuple[str, ...] | None = None) -> HarmonicInversion:
    """Solve for the depth harmonics from one measured response.

    Unknowns are ``[Re d_1, Im d_1, Re d_2, ...]``.  Each order contributes two
    equations (the in-phase and quadrature parts of its line), so ``N`` orders give
    ``2N`` equations for ``2N`` unknowns *without* mixing orders -- and that is the
    point: the rank deficiency that broke the band matrix came from asking one
    number per band; here every order is its own observable.

    An order whose gain sits below ``floor_gain`` is left out of the operator rather
    than entered as a near-zero row: a row of almost zeros would drag the posterior
    towards "no depth at all" with a falsely small sigma, whereas leaving it out keeps
    that order at the prior and reports the honesty of it.
    """

    orders = model.orders
    if not orders:
        raise HarmonicError("the model has no orders")
    if not math.isfinite(fundamental_hz) or fundamental_hz <= 0.0:
        raise HarmonicError(f"fundamental frequency must be positive; got {fundamental_hz!r}")
    if not math.isfinite(period_m) or period_m <= 0.0:
        raise HarmonicError(f"period must be positive; got {period_m!r}")
    silent = set(model.silent_orders(floor_gain)) if floor_gain > 0.0 else set()
    # An order with no measurement is *unobserved*, not measured as zero: entering a row
    # of zeros would pin that depth harmonic to zero with a falsely small sigma, which is
    # the difference between "we saw nothing there" and "there is nothing there".
    kept = [order for order in orders
            if order in measured and order not in silent and model.gains[order] != 0.0 + 0.0j]
    if not kept:
        raise HarmonicError(
            "every order's gain is in the floor; there is nothing to invert at this period")
    operator = np.zeros((2 * len(kept), 2 * len(orders)), dtype=float)
    rhs = np.zeros(2 * len(kept), dtype=float)
    for index, order in enumerate(kept):
        gain = model.gains[order]
        value = measured.get(order, 0.0 + 0.0j)
        position = 2 * orders.index(order)
        # (g_re + i g_im)(d_re + i d_im) = A e^{i phi}, written as two real rows.
        operator[2 * index, position] = gain.real
        operator[2 * index, position + 1] = -gain.imag
        rhs[2 * index] = float(value.real)
        operator[2 * index + 1, position] = gain.imag
        operator[2 * index + 1, position + 1] = gain.real
        rhs[2 * index + 1] = float(value.imag)
    posterior = weighted_least_squares(
        operator, rhs,
        measurement_sigma=measurement_sigma,
        prior_sigma=[prior_sigma] * (2 * len(orders)),
        prior_mean=[prior_mean] * (2 * len(orders)),
        labels=labels or tuple(f"d{order}{part}" for order in orders for part in ("_re", "_im")),
    )
    return HarmonicInversion(model=model, posterior=posterior, orders=orders,
                             fundamental_hz=float(fundamental_hz), period_m=float(period_m),
                             measured=dict(measured))


def coverage_across_orders(inversion: HarmonicInversion,
                           truth: dict[int, complex], k: float = 1.0) -> list[dict]:
    """Per-order check: is the true depth inside ``mean +- k sigma``?"""

    rows = []
    for position, order in enumerate(inversion.orders):
        estimated = complex(float(inversion.posterior.mean[2 * position]),
                            float(inversion.posterior.mean[2 * position + 1]))
        sigma = math.sqrt(
            max(float(inversion.posterior.covariance[2 * position, 2 * position]), 0.0)
            + max(float(inversion.posterior.covariance[2 * position + 1, 2 * position + 1]), 0.0))
        true_value = truth.get(order, 0.0 + 0.0j)
        distance = abs(estimated - true_value)
        rows.append({
            "order": order,
            "estimated_m": abs(estimated),
            "true_m": abs(true_value),
            "sigma_m": sigma,
            "inside": bool(distance <= k * sigma) if sigma > 0.0 else distance == 0.0,
            "z": distance / sigma if sigma > 0.0 else float("inf"),
        })
    return rows
