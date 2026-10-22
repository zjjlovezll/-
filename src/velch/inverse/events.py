"""Event descriptors: what a force or displacement pulse actually looks like.

Peak level alone cannot separate two structures (see ``identifiability``: the peak observable
has rank 1 for two parameters).  Rise time, decay time and the number of oscillations carry
the *shape*, and shape is what survives when the two objects are not identical - a rack-railway
vehicle crossing a No. 7 turnout can be compared with a CRH380A crossing a No. 18 turnout on
timing and shape, not on force value.

Everything here is descriptive: no physics, no fitting of the forward model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


class EventError(ValueError):
    """Raised when an event cannot be described from the data given."""


@dataclass(frozen=True)
class EventDescriptor:
    """Shape of one pulse, relative to a local baseline."""

    baseline: float
    peak: float
    amplitude: float
    peak_time_s: float
    rise_time_s: float
    decay_time_s: float
    oscillation_count: int
    window_s: float

    def report(self) -> dict[str, float | int]:
        return {
            "baseline": float(self.baseline),
            "peak": float(self.peak),
            "amplitude": float(self.amplitude),
            "peak_time_s": float(self.peak_time_s),
            "rise_time_s": float(self.rise_time_s),
            "decay_time_s": float(self.decay_time_s),
            "oscillation_count": int(self.oscillation_count),
            "window_s": float(self.window_s),
        }

    def summary(self, *, unit: str = "", label: str = "event") -> str:
        suffix = f" {unit}" if unit else ""
        return (f"{label}: baseline {self.baseline:.4g}{suffix} peak {self.peak:.4g}{suffix} "
                f"amplitude {self.amplitude:.4g}{suffix} at {self.peak_time_s:.4f} s; "
                f"rise {self.rise_time_s * 1e3:.3f} ms decay {self.decay_time_s * 1e3:.3f} ms; "
                f"{self.oscillation_count} oscillation(s)")


def describe_event(time_s: Sequence[float], values: Sequence[float], *, index: int | None = None,
                   baseline_fraction: float = 0.1, window_s: float | None = None,
                   threshold_fraction: float = 0.1) -> EventDescriptor:
    """Describe the largest excursion of ``values`` around a local baseline.

    ``baseline`` is the median of the first ``baseline_fraction`` of the record (the quiet
    part before the pass).  The amplitude is signed: a compressive pulse stays negative.
    ``rise_time`` is the 10 %-to-peak climb and ``decay_time`` is the peak-to-10 % fall, so
    both are durations, not time stamps, and a symmetric pulse gives equal values.
    """
    time = np.asarray(time_s, dtype=float)
    data = np.asarray(values, dtype=float)
    if time.ndim != 1 or data.ndim != 1 or time.size != data.size:
        raise EventError("time and values must be 1-D and the same length")
    if time.size < 8:
        raise EventError(f"need at least 8 samples, got {time.size}")
    if not (0.0 < baseline_fraction <= 1.0):
        raise EventError("baseline_fraction must be in (0, 1]")
    if not (0.0 < threshold_fraction < 1.0):
        raise EventError("threshold_fraction must be in (0, 1)")
    step = float(np.median(np.diff(time)))
    if not np.isfinite(step) or step <= 0.0:
        raise EventError("time must be strictly increasing")
    if not np.all(np.isfinite(data)):
        raise EventError("values must be finite")

    head = max(int(round(baseline_fraction * time.size)), 4)
    baseline = float(np.median(data[:head]))
    deviation = data - baseline
    if index is None:
        index = int(np.argmax(np.abs(deviation)))
    if not (0 <= index < data.size):
        raise EventError(f"index {index} outside the record")
    amplitude = float(deviation[index])
    if amplitude == 0.0:
        raise EventError("flat record: amplitude is zero")

    sign = np.sign(amplitude)
    profile = sign * deviation
    height = abs(amplitude)

    # rise: last crossing of 10 % before the peak -> last crossing of 90 % before the peak
    def last_crossing(level: float, stop: int) -> float | None:
        below = np.nonzero(profile[:stop] < level)[0]
        return float(time[below[-1]]) if below.size else None

    low = last_crossing(0.1 * height, index + 1)
    rise = float(time[index] - (low if low is not None else time[0]))

    # decay: from the peak until the envelope falls back under the threshold fraction
    stop = data.size
    if window_s is not None:
        stop = min(stop, int(np.searchsorted(time, time[index] + window_s)))
    tail = profile[index:stop]
    below = np.nonzero(tail < threshold_fraction * height)[0]
    decay = float(time[index + int(below[0])] - time[index]) if below.size else \
        float(time[stop - 1] - time[index])

    # Oscillations right after the peak are what distinguishes a ringing contact from a
    # clean pulse, so always look at least 64 samples (12.5 ms at 5.12 kHz) past the peak,
    # even when the envelope decays under the threshold sooner than that.
    span = max(int(below[0]) if below.size else tail.size, min(64, tail.size))
    after = tail[:span]
    crossings = int(np.count_nonzero(np.diff(np.sign(after)) != 0))
    return EventDescriptor(baseline=baseline, peak=float(data[index]), amplitude=amplitude,
                           peak_time_s=float(time[index]), rise_time_s=max(rise, step),
                           decay_time_s=max(decay, step), oscillation_count=crossings,
                           window_s=float(time[stop - 1] - time[index]))


def compare_shapes(reference: EventDescriptor, candidate: EventDescriptor) -> dict[str, float]:
    """Ratios candidate/reference for the shape quantities that are scale-free.

    Only ratios of *durations* and of the oscillation count are reported: the amplitudes belong
    to different vehicles on different turnouts and must not be divided.
    """
    if reference.rise_time_s <= 0.0 or reference.decay_time_s <= 0.0:
        raise EventError("reference durations must be positive")
    return {
        "rise_ratio": candidate.rise_time_s / reference.rise_time_s,
        "decay_ratio": candidate.decay_time_s / reference.decay_time_s,
        "oscillation_ratio": (candidate.oscillation_count + 1.0)
        / (reference.oscillation_count + 1.0),
        "amplitude_ratio_not_comparable": candidate.amplitude / reference.amplitude,
    }
