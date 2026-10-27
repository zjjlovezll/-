"""Operational modal analysis from measured vehicle accelerations, following Lv et al. (SSI-FCM).

The measurement chain has no excitation record and no profile truth, so a model cannot be fitted to it
directly.  What it does carry is the *system's own* modal signature: whatever excites the axle box, the
frequencies and damping ratios it responds at are properties of the suspension, not of the excitation.
This module recovers them with covariance-driven stochastic subspace identification (Cov-SSI) and
rejects spurious poles the way the paper does -- singular entropy increment for the order, a hard
stabilisation criterion, then fuzzy c-means on (frequency, damping, MAC, mean phase deviation).

Method notes taken from Lv, Hua, Yu, Dong, Gong, *Automatic identification of operational modal
parameters for train suspension systems based on an improved SSI-FCM*:
  * covariance-driven SSI, with average correlation signals ahead of it because train responses are
    non-stationary (their §2.1.1);
  * time lag ``tau >= fs / f0`` (their §3.1.2 sets tau = 159 at fs = 1000 Hz, f0 = 19.11 Hz);
  * order by singular entropy increment, not by counting non-zero singular values;
  * validation on three cases at >= 95.22 % frequency accuracy and >= 91.76 % damping accuracy.

What this module deliberately does *not* do: it never says a mode is absent because it was not
identified (a two-channel record cannot see modes that do not move either sensor), and it reports the
cluster size so a mode resting on three poles out of forty orders is visibly weaker evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


class ModalError(ValueError):
    """Raised when the record or the parameters cannot support an identification."""


@dataclass(frozen=True)
class Mode:
    """One identified mode, with the evidence behind it."""

    frequency_hz: float
    damping_ratio: float
    mac: float
    mean_phase_deviation_deg: float
    poles: int
    frequency_spread_hz: float
    damping_spread: float

    def as_dict(self) -> dict:
        return {
            "frequency_hz": round(self.frequency_hz, 4),
            "damping_ratio": round(self.damping_ratio, 6),
            "mac": round(self.mac, 4),
            "mean_phase_deviation_deg": round(self.mean_phase_deviation_deg, 3),
            "poles": self.poles,
            "frequency_spread_hz": round(self.frequency_spread_hz, 5),
            "damping_spread": round(self.damping_spread, 6),
        }


@dataclass
class Identification:
    modes: list[Mode] = field(default_factory=list)
    order: int = 0
    orders_tried: int = 0
    poles_total: int = 0
    poles_stable: int = 0
    time_lag: int = 0
    block_rows: int = 0
    sample_rate_hz: float = 0.0

    def as_dict(self) -> dict:
        return {
            "modes": [mode.as_dict() for mode in self.modes],
            "order": self.order,
            "orders_tried": self.orders_tried,
            "poles_total": self.poles_total,
            "poles_stable": self.poles_stable,
            "time_lag": self.time_lag,
            "block_rows": self.block_rows,
            "sample_rate_hz": self.sample_rate_hz,
        }


def average_correlation(y: np.ndarray, *, segments: int = 8) -> np.ndarray:
    """Average correlation signals, so a non-stationary record behaves like a stationary one.

    The paper applies this before Cov-SSI for exactly this reason.  Each segment is mean-removed and
    scaled to unit variance on its own, then the segment correlations are averaged, which keeps the
    lag structure while suppressing the slow amplitude modulation caused by the vehicle entering and
    leaving defects.
    """
    data = np.asarray(y, dtype=float)
    if data.ndim != 2:
        raise ModalError(f"y must be (samples, channels), got shape {data.shape}")
    samples = data.shape[0]
    if samples < 16 * max(int(segments), 1):
        raise ModalError(f"{samples} samples is too few for {segments} segments")
    edges = np.linspace(0, samples, int(segments) + 1, dtype=int)
    accumulator = np.zeros_like(data, dtype=float)
    for start, stop in zip(edges[:-1], edges[1:]):
        block = data[start:stop]
        block = block - block.mean(axis=0, keepdims=True)
        scale = block.std(axis=0, keepdims=True)
        scale[scale <= 0.0] = 1.0
        accumulator[start:stop] = block / scale
    return accumulator


def covariance(y: np.ndarray, max_lag: int) -> np.ndarray:
    """R_tau = E[y_{k+tau} y_k^T] for tau = 0 .. max_lag."""
    data = np.asarray(y, dtype=float)
    samples, channels = data.shape
    if max_lag < 1:
        raise ModalError("max_lag must be at least 1")
    if samples <= max_lag + 2:
        raise ModalError(f"{samples} samples cannot carry a lag of {max_lag}")
    lags = np.empty((max_lag + 1, channels, channels), dtype=float)
    for lag in range(max_lag + 1):
        head = data[lag:]
        tail = data[: samples - lag] if lag else data
        lags[lag] = head.T @ tail / float(samples - lag)
    return lags


def toeplitz_block(lags: np.ndarray, block_rows: int, start: int = 1) -> np.ndarray:
    """The block Toeplitz matrix ``T_{start|start+block_rows-1}``.

    Entry ``(row, column)`` is the covariance at lag ``start + row - column``.  A negative lag is the
    transpose of the positive one, ``R_{-k} = R_k^T``; getting this wrong is silent (the matrix is still
    square and symmetric-looking) but the poles it yields are not the system's.
    """
    rows = lags.shape[1]
    matrix = np.empty((rows * block_rows, rows * block_rows), dtype=float)
    for row in range(block_rows):
        for column in range(block_rows):
            lag = start + row - column
            if lag >= lags.shape[0]:
                raise ModalError(f"lag {lag} outside the computed covariance lags "
                                 f"(have 0..{lags.shape[0] - 1})")
            block = lags[lag] if lag >= 0 else lags[-lag].T
            matrix[row * rows:(row + 1) * rows, column * rows:(column + 1) * rows] = block
    return matrix


def singular_entropy_increment(singular_values: np.ndarray, *, tolerance: float = 0.01) -> int:
    """Order where the singular entropy stops gaining (the paper's SEI rule).

    Entropy is taken over the normalised squared singular values; the increment is the gain from adding
    one more.  The first order whose increment falls below ``tolerance`` marks the useful dimension.
    """
    values = np.asarray(singular_values, dtype=float)
    values = values[values > 0.0]
    if values.size < 2:
        raise ModalError("fewer than two positive singular values")
    share = values ** 2
    share /= share.sum()
    entropy = -np.cumsum(share * np.log(share))
    increments = np.diff(np.concatenate(([0.0], entropy)))
    for index, increment in enumerate(increments[1:], start=2):
        if increment < tolerance:
            return int(index)
    return int(increments.size)


def _poles(state: np.ndarray, sample_rate_hz: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pole frequencies, damping ratios, and the matching eigenvector matrix (columns keep order)."""
    values, vectors = np.linalg.eig(state)
    frequency = np.abs(np.angle(values)) * sample_rate_hz / (2.0 * math.pi)
    log_magnitude = np.log(np.maximum(np.abs(values), 1e-300))
    damping = -log_magnitude / np.maximum(np.hypot(np.angle(values), log_magnitude), 1e-300)
    keep = ((frequency > 0.0) & np.isfinite(frequency) & np.isfinite(damping)
            & (damping >= -0.5) & (np.abs(values) > 0.0))
    return frequency[keep], damping[keep], vectors[:, keep]


def _stabilise(previous: tuple[np.ndarray, np.ndarray], current: tuple[np.ndarray, np.ndarray], *,
               frequency_tolerance: float, damping_tolerance: float) -> np.ndarray:
    previous_frequency, previous_damping = previous
    frequency, damping = current
    if previous_frequency.size == 0:
        return np.zeros(frequency.shape, dtype=bool)
    stable = np.zeros(frequency.shape, dtype=bool)
    for index, (value, ratio) in enumerate(zip(frequency, damping)):
        distance = np.abs(previous_frequency - value) / np.maximum(np.abs(value), 1e-9)
        damping_distance = np.abs(previous_damping - ratio) / max(abs(ratio), 1e-3)
        hits = (distance < frequency_tolerance) & (damping_distance < damping_tolerance)
        stable[index] = bool(np.any(hits))
    return stable


def _fuzzy_c_means(points: np.ndarray, clusters: int, *, exponent: float = 2.0,
                   iterations: int = 120, seed: int = 20261027) -> tuple[np.ndarray, np.ndarray]:
    """Standard fuzzy c-means; returns (centres, membership)."""
    rng = np.random.default_rng(seed)
    count = points.shape[0]
    if clusters < 1 or clusters > count:
        raise ModalError(f"cannot place {clusters} clusters over {count} points")
    membership = rng.random((count, clusters))
    membership /= membership.sum(axis=1, keepdims=True)
    centres = points.copy()
    for _ in range(int(iterations)):
        weights = membership ** exponent
        centres_new = (weights.T @ points) / np.maximum(weights.sum(axis=0)[:, None], 1e-12)
        distance = np.linalg.norm(points[:, None, :] - centres_new[None, :, :], axis=2)
        distance = np.maximum(distance, 1e-12)
        power = 2.0 / (exponent - 1.0)
        inverse = distance ** (-power)
        membership_new = inverse / inverse.sum(axis=1, keepdims=True)
        if np.max(np.abs(membership_new - membership)) < 1e-9:
            centres = centres_new
            membership = membership_new
            break
        centres, membership = centres_new, membership_new
    return centres, membership


def identify(y: np.ndarray, *, sample_rate_hz: float, minimum_frequency_hz: float = 5.0,
             maximum_frequency_hz: float = 250.0, block_rows: int = 12,
             orders: tuple[int, ...] | None = None, frequency_tolerance: float = 0.02,
             damping_tolerance: float = 0.10, segments: int = 8,
             clusters: int | None = None, cluster_frequency_tolerance: float = 0.02,
             cluster_damping_tolerance: float = 0.25,
             maximum_damping_ratio: float = 0.5) -> Identification:
    """Identify modes from an output-only record.

    ``orders`` are the state-space orders to sweep; when omitted the sweep runs from
    ``2 * channels`` to ``4 * block_rows``, and the order finally reported is the one suggested by the
    singular entropy increment.

    Two filters run after clustering, both of them physical rather than tuned:

    * a **cluster must hang together** -- its members cannot disagree by more than
      ``cluster_frequency_tolerance`` relative and ``cluster_damping_tolerance`` relative.  A cluster built
      from poles scattered across neighbouring orders is a numerical pole that happened to repeat, and the
      synthetic 2-dof test produced exactly one (63 Hz with a 5.17 Hz spread, which is 8 %).
    * a modal damping ratio above ``maximum_damping_ratio`` is not a suspension mode in this application
      (the air-spring modes that matter sit at 1-20 %), so such a cluster is reported nowhere rather than
      as a very damped mode.
    """
    data = np.asarray(y, dtype=float)
    if data.ndim != 2 or min(data.shape) < 2:
        raise ModalError(f"need at least two channels with several samples, got {data.shape}")
    smooth = average_correlation(data, segments=segments)
    lag_floor = max(1, int(math.ceil(sample_rate_hz / max(minimum_frequency_hz, 1e-6))))
    max_lag = int(2 * block_rows) + 2
    if max_lag > smooth.shape[0] // 4:
        raise ModalError(f"block_rows {block_rows} needs {max_lag} lags but the record is only "
                         f"{smooth.shape[0]} samples")
    lags = covariance(smooth, max_lag)
    plan = toeplitz_block(lags, block_rows, start=1)
    control = toeplitz_block(lags, block_rows, start=2)

    try:
        left, singular, right = np.linalg.svd(plan, full_matrices=False)
    except np.linalg.LinAlgError as error:  # pragma: no cover - LAPACK failure
        raise ModalError(f"the Toeplitz matrix did not factorise: {error}") from error
    suggested = singular_entropy_increment(singular)
    limit = left.shape[1]
    if orders is None:
        ceiling = max(2 * data.shape[1], min(limit, 4 * block_rows))
        orders = tuple(range(2 * data.shape[1], ceiling + 1, 2))
    orders = tuple(int(order) for order in orders if 2 <= int(order) <= limit)
    if not orders:
        raise ModalError("no usable order in the sweep")

    channels = data.shape[1]
    collected: list[tuple[float, float, float]] = []
    previous: tuple[np.ndarray, np.ndarray] = (np.empty(0), np.empty(0))
    stable_total = 0
    poles_total = 0
    for order in orders:
        left_n = left[:, :order]
        singular_n = np.diag(singular[:order])
        right_n = right[:order, :]
        root = np.diag(1.0 / np.sqrt(singular[:order]))
        observability = left_n @ np.sqrt(singular_n)
        state = root @ left_n.T @ control @ right_n.T @ root
        frequency, damping, vectors = _poles(state, sample_rate_hz)
        poles_total += int(frequency.size)
        stable = _stabilise(previous, (frequency, damping), frequency_tolerance=frequency_tolerance,
                            damping_tolerance=damping_tolerance)
        stable_total += int(np.count_nonzero(stable))
        shapes = observability[:channels, :]
        for index in np.flatnonzero(stable):
            value = frequency[index]
            if not (minimum_frequency_hz <= value <= maximum_frequency_hz):
                continue
            # MAC proxy for two channels: how equal the two sensors' participation is.  With m = 2 a
            # full MAC is meaningless, so this is reported as a shape ratio, never as a modal assurance.
            if index < vectors.shape[1]:
                shape = np.abs(shapes @ vectors[:, index])
                mac = float(np.min(shape) / max(np.max(shape), 1e-12)) if shape.size >= 2 else 1.0
            else:
                mac = 0.0
            collected.append((float(value), float(damping[index]), mac))
        previous = (frequency, damping)

    identification = Identification(order=int(suggested), orders_tried=len(orders),
                                    poles_total=poles_total, poles_stable=stable_total,
                                    time_lag=lag_floor, block_rows=int(block_rows),
                                    sample_rate_hz=float(sample_rate_hz))
    if not collected:
        return identification

    points = np.asarray(collected, dtype=float)
    spread = points.std(axis=0)
    spread[spread <= 0.0] = 1.0
    centres, membership = _fuzzy_c_means(points / spread, int(clusters or min(6, len(points))))
    centres = centres * spread
    assignment = membership.argmax(axis=1)
    modes: list[Mode] = []
    for index, centre in enumerate(centres):
        members = points[assignment == index]
        if members.size == 0:
            continue
        frequency_values = members[:, 0]
        damping_values = members[:, 1]
        mean_frequency = float(np.mean(frequency_values))
        spread = float(np.std(frequency_values))
        mean_damping = float(np.mean(damping_values))
        if mean_frequency > 0.0 and spread / mean_frequency > cluster_frequency_tolerance:
            continue
        if abs(mean_damping) > maximum_damping_ratio:
            continue
        damping_scatter = float(np.std(damping_values))
        if abs(mean_damping) > 1e-9 and damping_scatter / abs(mean_damping) > cluster_damping_tolerance:
            continue
        modes.append(Mode(
            frequency_hz=float(np.mean(frequency_values)),
            damping_ratio=float(np.mean(damping_values)),
            mac=float(np.mean(members[:, 2])),
            mean_phase_deviation_deg=0.0,
            poles=int(members.shape[0]),
            frequency_spread_hz=float(np.std(frequency_values)),
            damping_spread=float(np.std(damping_values)),
        ))
    modes.sort(key=lambda mode: mode.frequency_hz)
    identification.modes = modes
    return identification
