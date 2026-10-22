"""Band-limited metrics, in the convention the measured campaign uses.

Every comparison that mixes a simulation with the ``E:/齿轨测试数据`` campaign must go through the
same numbers, so this module reproduces the campaign's stated convention rather than inventing a
new one:

* analysis band **5-1000 Hz**, 4th-order Butterworth, zero-phase (``sosfiltfilt``);
* 1/3-octave bands covering that range;
* the reported triple is peak / peak-to-peak / RMS, plus the 1/3-octave band that carries the most
  energy (the campaign's tables report "峰值频带" and its level).

The campaign also warns that its per-channel maxima are single events (``CH04`` max/median = 22-34),
so median and p99.9 are carried alongside the maximum: a maximum alone is not a level.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

DEFAULT_BAND_HZ = (5.0, 1000.0)
THIRD_OCTAVE_BASE = 2.0 ** (1.0 / 3.0)


class BandError(ValueError):
    """Raised when a band computation cannot be formed from the given data."""


def third_octave_centres(low_hz: float = DEFAULT_BAND_HZ[0],
                         high_hz: float = DEFAULT_BAND_HZ[1]) -> tuple[float, ...]:
    """1/3-octave centre frequencies covering ``[low_hz, high_hz]``.

    Anchored on 1000 Hz (the standard reference) and walked downwards/upwards, so the centres are
    the same numbers the campaign's PSD integration uses.
    """

    if low_hz <= 0.0 or high_hz <= low_hz:
        raise BandError("band limits must satisfy 0 < low < high")
    anchor = 1000.0
    step = math.log(THIRD_OCTAVE_BASE)
    start = math.ceil(math.log(low_hz / anchor) / step - 1e-12)
    stop = math.floor(math.log(high_hz / anchor) / step + 1e-12)
    return tuple(anchor * math.exp(step * n) for n in range(start, stop + 1))


def bandpass(values: np.ndarray, rate_hz: float, low_hz: float = DEFAULT_BAND_HZ[0],
             high_hz: float = DEFAULT_BAND_HZ[1], order: int = 4) -> np.ndarray:
    """Zero-phase Butterworth band-pass; returns the input unchanged when data are too short."""

    data = np.asarray(values, float)
    if data.ndim != 1:
        raise BandError("bandpass expects a one-dimensional series")
    if rate_hz <= 0.0:
        raise BandError("rate must be positive")
    nyquist = 0.5 * rate_hz
    if high_hz >= nyquist:
        high_hz = 0.999 * nyquist
    if low_hz <= 0.0 or low_hz >= high_hz:
        raise BandError("band limits must satisfy 0 < low < high < nyquist")
    if data.shape[0] <= 3 * order * 2:
        return data.copy()

    from scipy.signal import butter, sosfiltfilt  # local import keeps module import cheap

    # A narrow *low* edge (5 Hz at 2 kHz) rings for about a second at the record boundary, and the
    # default odd padding leaves that ring inside the data where it inflates every extremum.
    # Padding by one second of odd extension puts the artefact outside the record instead.
    pad = int(min(data.shape[0] // 2 - 1, max(0, 2.0 * rate_hz)))
    padlen = pad if pad > 0 else None
    # The upper edge sits at ``0.999 * nyquist`` by default.  On a *short* window scipy's stability
    # check can reject that section outright with ``Filter not stable due to sum(a) == 0`` -- the
    # same filter is fine on a long record, so retry narrower instead of refusing a 70-sample window.
    for edge in (high_hz, 0.97 * nyquist, 0.90 * nyquist):
        if edge <= low_hz:
            break
        sos = butter(order, (low_hz / nyquist, edge / nyquist), btype="bandpass", output="sos")
        try:
            return sosfiltfilt(sos, data, padlen=padlen)
        except ValueError as error:
            if "not stable" not in str(error):
                raise
    raise BandError("band-pass filter is unstable for this window and rate")


def _trimmed(values: np.ndarray, rate_hz: float, low_hz: float) -> np.ndarray:
    """Drop the zero-phase filter's settling transient before reading extrema or RMS.

    A zero-phase band-pass has a startup transient whose length is set by the *low* corner
    (about ``1/(2*low_hz)`` seconds).  Left in place it inflates peak-to-peak by tens of percent,
    which is exactly the mistake that makes two records look different when only their edges are.
    """

    data = np.asarray(values, float)
    settle = int(math.ceil(rate_hz / (2.0 * max(low_hz, 1e-6))))
    if data.shape[0] <= 4 * settle or settle == 0:
        return data
    return data[settle:-settle]


def band_rms(values: np.ndarray, rate_hz: float, low_hz: float,
             high_hz: float) -> float:
    """RMS of the series inside one band, ignoring the filter transient."""

    filtered = _trimmed(bandpass(values, rate_hz, low_hz, high_hz), rate_hz, low_hz)
    return float(np.sqrt(np.mean(filtered ** 2)))


def third_octave_levels(values: np.ndarray, rate_hz: float,
                        centres: tuple[float, ...] | None = None) -> dict[float, float]:
    """RMS per 1/3-octave band, using half-band edges of the centre frequencies."""

    data = np.asarray(values, float)
    if data.size < 8:
        raise BandError("too few samples for a third-octave decomposition")
    bands = centres if centres is not None else third_octave_centres()
    levels: dict[float, float] = {}
    for centre in bands:
        low, high = centre / THIRD_OCTAVE_BASE ** 0.5, centre * THIRD_OCTAVE_BASE ** 0.5
        if high >= 0.5 * rate_hz:
            continue
        levels[centre] = band_rms(data, rate_hz, low, high)
    if not levels:
        raise BandError("no third-octave band fits below Nyquist")
    return levels


def acceleration_from_position(position_m: np.ndarray, rate_hz: float) -> np.ndarray:
    """Second difference of a uniformly sampled position series.

    Output resolution in the solved cases is 2 kHz, so this is usable up to a few hundred Hz --
    enough for the campaign's 100-1000 Hz energy band, and cheaper than re-integrating the model
    just to read accelerations.
    """

    data = np.asarray(position_m, float)
    if data.shape[0] < 3:
        raise BandError("need at least three samples to differentiate twice")
    if rate_hz <= 0.0:
        raise BandError("rate must be positive")
    return np.gradient(np.gradient(data, 1.0 / rate_hz), 1.0 / rate_hz)


@dataclass(frozen=True)
class BandMetrics:
    """What the campaign reports for one channel, plus the robust companions."""

    peak: float
    peak_to_peak: float
    rms: float
    median_abs: float
    p999_abs: float
    dominant_band_hz: float | None = None
    band_rms: dict[float, float] = field(default_factory=dict)

    def summary(self, unit: str = "") -> str:
        suffix = f" {unit}" if unit else ""
        band = "-" if self.dominant_band_hz is None else f"{self.dominant_band_hz:.0f} Hz"
        return (f"peak {self.peak:.3f}{suffix}  p-p {self.peak_to_peak:.3f}  "
                f"rms {self.rms:.3f}  median|x| {self.median_abs:.3f}  "
                f"p99.9 {self.p999_abs:.3f}  dominant {band}")


def band_metrics(values: np.ndarray, rate_hz: float,
                 low_hz: float = DEFAULT_BAND_HZ[0],
                 high_hz: float = DEFAULT_BAND_HZ[1]) -> BandMetrics:
    """The full campaign-style metric set for one channel."""

    filtered = _trimmed(bandpass(values, rate_hz, low_hz, high_hz), rate_hz, low_hz)
    levels = third_octave_levels(filtered, rate_hz)
    dominant = max(levels, key=lambda centre: levels[centre])
    return BandMetrics(
        peak=float(np.max(np.abs(filtered))),
        peak_to_peak=float(filtered.max() - filtered.min()),
        rms=float(np.sqrt(np.mean(filtered ** 2))),
        median_abs=float(np.median(np.abs(filtered))),
        p999_abs=float(np.percentile(np.abs(filtered), 99.9)),
        dominant_band_hz=float(dominant),
        band_rms=levels,
    )
