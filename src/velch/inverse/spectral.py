"""Frequency-domain decomposition (FDD) for output-only records whose excitation is broadband impacts.

Cov-SSI (``velch.inverse.oma``) fits a state-space model to the covariance sequence, which assumes the
response is dominated by a handful of decaying modes.  A measured axle-box record is not like that: the
impact of a corrugated or dipped rail dominates, the effective rank collapses (a singular entropy order of
5 on a 24 x 24 Toeplitz matrix), and successive sections agreed on nothing.

FDD makes a weaker assumption, which is exactly what such a record can support: at a resonance the spectral
matrix of the outputs is rank one, so the first singular value of ``S(f)`` peaks and the matching singular
vector *is* the mode shape.  It never fits a model, so it cannot invent a mode that no section repeats --
which is the criterion this project needs, because a mode that appears in one section and not in the next
is not a property of the vehicle.

References for the method: Brincker, Zhang & Andersen, *Modal identification of output-only systems using
frequency domain decomposition* (Smart Materials and Structures 10, 2001); the complex-mode extension is
EFDD, whose damping estimate is not implemented here -- a damping ratio from a 2-channel peak is not
identifiable, and reporting one would be the kind of number this project keeps having to retract.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


class SpectralError(ValueError):
    """Raised when a record or a parameter cannot support a decomposition."""


@dataclass(frozen=True)
class Peak:
    """One spectral peak, with the evidence that it is a mode rather than noise."""

    frequency_hz: float
    singular_value: float
    prominence_db: float
    shape: tuple[float, ...]
    shape_ratio: float
    upper_singular_ratio: float

    def as_dict(self) -> dict:
        return {
            "frequency_hz": round(self.frequency_hz, 4),
            "singular_value": float(self.singular_value),
            "prominence_db": round(self.prominence_db, 3),
            "shape": [round(float(value), 4) for value in self.shape],
            "shape_ratio": round(self.shape_ratio, 4),
            "upper_singular_ratio": round(self.upper_singular_ratio, 4),
        }


@dataclass
class Decomposition:
    frequencies: np.ndarray
    singular_values: np.ndarray          # (channels, frequencies)
    peaks: list[Peak] = field(default_factory=list)
    segment_seconds: float = 0.0
    resolution_hz: float = 0.0
    sample_rate_hz: float = 0.0
    shapes: list[np.ndarray] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "peaks": [peak.as_dict() for peak in self.peaks],
            "segment_seconds": self.segment_seconds,
            "resolution_hz": self.resolution_hz,
            "sample_rate_hz": self.sample_rate_hz,
            "frequency_range_hz": [float(self.frequencies[0]), float(self.frequencies[-1])],
        }


def spectral_matrix(y: np.ndarray, *, sample_rate_hz: float, segment_seconds: float = 2.0,
                    overlap: float = 0.5, band: tuple[float, float] | None = (5.0, 200.0),
                    detrend: bool = True) -> Decomposition:
    """SVD of the averaged cross-spectral matrix, frequency by frequency."""
    from scipy.signal import csd, detrend as scipy_detrend

    data = np.asarray(y, dtype=float)
    if data.ndim != 2 or min(data.shape) < 2:
        raise SpectralError(f"need at least two channels with several samples, got {data.shape}")
    samples = data.shape[0]
    nperseg = int(round(float(segment_seconds) * sample_rate_hz))
    if nperseg < 32:
        raise SpectralError(f"a {segment_seconds} s segment is too short at {sample_rate_hz} Hz")
    if nperseg > samples:
        raise SpectralError(f"a {segment_seconds} s segment needs {nperseg} samples but the record has "
                            f"{samples}; shorten segment_seconds")
    if not 0.0 <= overlap < 1.0:
        raise SpectralError(f"overlap must be in [0, 1), got {overlap}")
    if detrend:
        data = scipy_detrend(data, axis=0, type="constant")

    channels = data.shape[1]
    freq = None
    matrix = np.zeros((channels, channels, 0), dtype=complex)
    blocks: list[np.ndarray] = []
    for row in range(channels):
        for column in range(channels):
            if column < row:
                continue
            freq, cross = csd(data[:, row], data[:, column], fs=sample_rate_hz, nperseg=nperseg,
                              noverlap=int(nperseg * overlap), detrend=False, scaling="density")
            blocks.append((row, column, cross))
    if freq is None:
        raise SpectralError("no spectral estimate was produced")
    matrix = np.zeros((channels, channels, freq.size), dtype=complex)
    for row, column, cross in blocks:
        matrix[row, column, :] = cross
        if row != column:
            matrix[column, row, :] = np.conj(cross)

    keep = np.ones(freq.shape, dtype=bool)
    if band is not None:
        low, high = band
        keep = (freq >= low) & (freq <= high)
    if np.count_nonzero(keep) < 4:
        raise SpectralError(f"band {band} leaves fewer than four frequency lines")
    # Keep the raw (dimensional) spectra: dividing by the trace at each line would flatten exactly the
    # contrast the peak search needs.  Measured: with the trace normalisation the first singular value sat
    # near 0.9 at *every* line of a two-channel record, so no peak cleared any prominence threshold.
    usable = matrix[:, :, keep]
    singular = np.zeros((channels, int(np.count_nonzero(keep))), dtype=float)
    shapes: list[np.ndarray] = []
    for index in range(usable.shape[2]):
        values, vectors = np.linalg.eigh(usable[:, :, index])
        order = np.argsort(values)[::-1]
        singular[:, index] = np.sqrt(np.maximum(values[order], 0.0))
        shapes.append(np.abs(vectors[:, order[0]]))
    decomposition = Decomposition(
        frequencies=freq[keep], singular_values=singular, segment_seconds=float(segment_seconds),
        resolution_hz=float(freq[1] - freq[0]), sample_rate_hz=float(sample_rate_hz),
    )
    decomposition.shapes = shapes
    return decomposition


def find_peaks(decomposition: Decomposition, *, prominence_db: float = 3.0,
               separation_hz: float | None = None, maximum_peaks: int = 12) -> list[Peak]:
    """Peaks of the first singular value, with the rank-one quality of each one attached."""
    values = decomposition.singular_values
    if values.size == 0:
        raise SpectralError("the decomposition carries no frequencies")
    first = values[0]
    frequencies = decomposition.frequencies
    separation = float(separation_hz if separation_hz is not None
                       else max(2.0 * decomposition.resolution_hz, 1.5))
    shapes = getattr(decomposition, "shapes", None)

    # Lines at the numerical floor are not peaks: a pure tone leaves most lines at ~1e-13 while its own
    # line sits at ~1e-3, and without this floor a zero line wins the prominence contest by dividing by a
    # floor that is equally zero.
    absolute = 1e-9 * float(np.max(first))

    peaks: list[Peak] = []
    for index in range(1, len(first) - 1):
        if first[index] < absolute:
            continue
        if not (first[index] >= first[index - 1] and first[index] >= first[index + 1]):
            continue
        # A robust floor: the lower quartile, because a two-channel record can put the first singular
        # value near the top of its range at most lines and a median would then sit almost on the peak.
        floor = float(np.percentile(first, 25))
        if floor <= 0.0:
            continue
        prominence = 20.0 * math.log10(max(first[index], 1e-300) / floor)
        if prominence < prominence_db:
            continue
        if any(abs(frequencies[index] - existing.frequency_hz) < separation for existing in peaks):
            continue
        shape = np.asarray(shapes[index]) if shapes is not None else np.ones(values.shape[0])
        shape_ratio = float(np.min(shape) / max(np.max(shape), 1e-12)) if shape.size > 1 else 1.0
        upper = float(values[1, index]) if values.shape[0] > 1 else 0.0
        peaks.append(Peak(frequency_hz=float(frequencies[index]),
                          singular_value=float(first[index]), prominence_db=float(prominence),
                          shape=tuple(float(value) for value in shape), shape_ratio=shape_ratio,
                          upper_singular_ratio=upper / max(float(first[index]), 1e-300)))
    peaks.sort(key=lambda peak: peak.singular_value, reverse=True)
    peaks = peaks[: int(maximum_peaks)]
    peaks.sort(key=lambda peak: peak.frequency_hz)
    decomposition.peaks = peaks
    return peaks
