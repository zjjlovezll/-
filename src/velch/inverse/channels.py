"""Measured-channel contract: the sensors a turnout campaign actually deploys.

The four sensor families the field programme provides are axle-box acceleration, rail
acceleration, rail web/foot strain (used to reconstruct the wheel-rail force) and
displacement. Each needs a different conversion before it can be compared with a
solver channel, so the conversions live here rather than in ad-hoc scripts:

* acceleration  -> already a comparison channel (m/s^2)
* strain        -> bending moment -> vertical wheel force, via a *measured* calibration
                   factor or via the section and influence-line geometry
* displacement  -> gap/deflection in metres

Strain-to-force deserves a warning: a single gauge does not measure a force, it measures
a local bending strain. Turning it into a wheel load requires (a) the gauge's position
relative to the wheel path (the influence ordinate) and (b) the rail section. Both are
stated explicitly here; nothing is silently assumed, and the calibration path is the
default because a static load test is what a real campaign uses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np

from .observation import ChannelSpec, ObservationError, ObservationSet


class ChannelContractError(ValueError):
    """Raised when a measured channel cannot be converted consistently."""


# --------------------------------------------------------------------------------------
# sensor plan
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SensorChannel:
    """One physical sensor channel: what it measures, how often, how precisely."""

    name: str
    kind: str
    unit: str
    sample_rate_hz: float
    sigma: float
    role: str = "data"
    location: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ("acceleration", "strain", "displacement", "force"):
            raise ChannelContractError(f"unknown sensor kind {self.kind!r}")
        if self.sample_rate_hz <= 0:
            raise ChannelContractError(f"{self.name}: sample rate must be positive")
        if self.sigma < 0:
            raise ChannelContractError(f"{self.name}: sigma must not be negative")

    def spec(self) -> ChannelSpec:
        return ChannelSpec(self.name, self.unit, role=self.role, sigma=self.sigma,
                           frame=self.location or "track",
                           sample_rate_hz=self.sample_rate_hz)


@dataclass(frozen=True)
class SensorPlan:
    """The channel list of one measurement campaign."""

    channels: tuple[SensorChannel, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        names = [channel.name for channel in self.channels]
        if len(set(names)) != len(names):
            raise ChannelContractError("duplicate sensor channel names")

    def __iter__(self):
        return iter(self.channels)

    def by_kind(self, kind: str) -> tuple[SensorChannel, ...]:
        return tuple(c for c in self.channels if c.kind == kind)

    def specs(self, role: str | None = None) -> tuple[ChannelSpec, ...]:
        chosen = self.channels if role is None else tuple(c for c in self.channels
                                                         if c.role == role)
        return tuple(channel.spec() for channel in chosen)

    @property
    def sample_rate_hz(self) -> float:
        return max((c.sample_rate_hz for c in self.channels), default=0.0)


def standard_turnout_plan(*, axle_boxes: Sequence[int] = (1, 2, 3, 4),
                          strain_gauge_n_per_microstrain: float = 1.0e4,
                          strain_sigma_n_per_microstrain: float = 50.0,
                          include_rail_acceleration: bool = True,
                          include_displacement: bool = True) -> SensorPlan:
    """The plan implied by the available instrumentation.

    Axle-box acceleration is triaxial per axle box at 2 kHz; rail acceleration is
    vertical at the crossing at 5 kHz; rail foot strain is converted to a vertical
    force by the calibration factor given (N per microstrain), which is what a static
    load test yields; displacement is a single vertical channel at the crossing nose.
    """

    if not axle_boxes:
        raise ChannelContractError("at least one axle box is required")
    channels: list[SensorChannel] = []
    for axle in axle_boxes:
        for axis in ("x", "y", "z"):
            channels.append(SensorChannel(
                name=f"axle{axle}_box_acc_{axis}", kind="acceleration", unit="m/s^2",
                sample_rate_hz=2000.0, sigma=0.05,
                location=f"axle{axle}_box"))
    if include_rail_acceleration:
        channels.append(SensorChannel(
            name="rail_acc_z_crossing", kind="acceleration", unit="m/s^2",
            sample_rate_hz=5000.0, sigma=0.2, role="check", location="crossing"))
    for side in ("left", "right"):
        channels.append(SensorChannel(
            name=f"{side}_rail_foot_strain",
            kind="strain", unit="N", sample_rate_hz=2000.0,
            sigma=strain_sigma_n_per_microstrain / strain_gauge_n_per_microstrain
            if strain_gauge_n_per_microstrain > 0 else 0.0,
            location=f"{side}_rail_foot"))
    if include_displacement:
        channels.append(SensorChannel(
            name="crossing_rail_disp_z", kind="displacement", unit="m",
            sample_rate_hz=1000.0, sigma=2.0e-5, role="check", location="crossing"))
    return SensorPlan(tuple(channels),
                      notes="rail-foot strain channels carry unit 'N' because they are "
                            "already converted by the calibration factor")


# --------------------------------------------------------------------------------------
# strain -> force
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class StrainCalibration:
    """Linear calibration of one strain channel into a vertical wheel force.

    ``force_n = n_per_microstrain * strain_microstrain + offset_n``. A static load test
    supplies the slope; the offset removes the instrument zero.
    """

    n_per_microstrain: float
    offset_n: float = 0.0
    provenance: str = ""

    def __post_init__(self) -> None:
        if self.n_per_microstrain == 0:
            raise ChannelContractError("calibration slope must not be zero")

    def force_n(self, strain_microstrain: np.ndarray | float):
        return self.n_per_microstrain * np.asarray(strain_microstrain, float) + self.offset_n

    def inverse(self, force_n: np.ndarray | float):
        return (np.asarray(force_n, float) - self.offset_n) / self.n_per_microstrain

    @classmethod
    def from_static_test(cls, strain_microstrain: Sequence[float],
                         force_n: Sequence[float],
                         provenance: str = "") -> "StrainCalibration":
        strains = np.asarray(strain_microstrain, float)
        loads = np.asarray(force_n, float)
        if strains.shape != loads.shape or strains.size < 2:
            raise ChannelContractError("static test needs at least two paired points")
        if np.ptp(strains) == 0:
            raise ChannelContractError("static test strain has no variation")
        slope, offset = np.polyfit(strains, loads, 1)
        return cls(float(slope), float(offset), provenance or "static load test")


def moment_from_strain(strain_microstrain: np.ndarray | float, *,
                       youngs_modulus_pa: float, second_moment_m4: float,
                       distance_to_extreme_fibre_m: float):
    """Bending moment from a surface strain (``M = eps * E * I / c``)."""

    if youngs_modulus_pa <= 0 or second_moment_m4 <= 0 or distance_to_extreme_fibre_m <= 0:
        raise ChannelContractError("section properties must be positive")
    strain = np.asarray(strain_microstrain, float) * 1.0e-6
    return strain * youngs_modulus_pa * second_moment_m4 / distance_to_extreme_fibre_m


def force_from_moment(moment_nm: np.ndarray | float, influence_ordinate_m: float):
    """Vertical wheel force from a bending moment via the influence ordinate.

    ``influence_ordinate_m`` is the moment (per unit load) produced at the gauge by a
    unit vertical load at the wheel's position — i.e. the ordinate of the rail's moment
    influence line at that station separation. It must be positive and non-zero; at a
    support the ordinate vanishes and the station is not usable for force reconstruction.
    """

    if influence_ordinate_m <= 0:
        raise ChannelContractError(
            "influence ordinate must be positive; choose a gauge station between supports")
    return np.asarray(moment_nm, float) / influence_ordinate_m


def influence_ordinate_simple_support(a_m: float, b_m: float, span_m: float) -> float:
    """Moment per unit load at gauge ``a`` for a unit vertical load at ``b``.

    Simply supported span of length ``L``::

        b <= a:  M/P = b * (L - a) / L
        b >= a:  M/P = a * (L - b) / L

    The ordinate is zero at either support, which is why a gauge placed over a sleeper
    cannot reconstruct a wheel load. A real campaign should replace this with the
    influence line of the actual sleeper spacing.
    """

    if span_m <= 0:
        raise ChannelContractError("span must be positive")
    if not (0.0 <= a_m <= span_m) or not (0.0 <= b_m <= span_m):
        raise ChannelContractError("positions must lie inside the span")
    if b_m <= a_m:
        return b_m * (span_m - a_m) / span_m
    return a_m * (span_m - b_m) / span_m


def strain_channel_to_force(strain_microstrain: np.ndarray, *,
                            calibration: StrainCalibration | None = None,
                            youngs_modulus_pa: float | None = None,
                            second_moment_m4: float | None = None,
                            distance_to_extreme_fibre_m: float | None = None,
                            influence_ordinate_m: float | None = None):
    """Convert a strain series into a vertical force, by calibration or by geometry.

    Exactly one route must be complete; mixing a partial geometric set with a
    calibration is allowed (the calibration wins) but a partial geometric set alone is
    an error rather than a silent fallback.
    """

    strain = np.asarray(strain_microstrain, float)
    if calibration is not None:
        return calibration.force_n(strain)
    geometric = (youngs_modulus_pa, second_moment_m4, distance_to_extreme_fibre_m,
                 influence_ordinate_m)
    if any(value is None for value in geometric):
        raise ChannelContractError(
            "give either a calibration or all of E, I, c and the influence ordinate")
    moment = moment_from_strain(strain, youngs_modulus_pa=youngs_modulus_pa,
                                second_moment_m4=second_moment_m4,
                                distance_to_extreme_fibre_m=distance_to_extreme_fibre_m)
    return force_from_moment(moment, influence_ordinate_m)


# --------------------------------------------------------------------------------------
# event detection (anchor for measured alignment)
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class DetectedEvent:
    time_s: float
    station_m: float | None
    channel: str
    amplitude: float
    index: int


def detect_peak_event(time_s: np.ndarray, values: np.ndarray, *,
                      channel: str, minimum: float | None = None,
                      prominence: float | None = None,
                      direction: str = "maximum",
                      speed_m_s: float | None = None,
                      station_at_zero_m: float = 0.0) -> DetectedEvent:
    """Detect the anchor event (crossing nose, switch throw) in a measured channel.

    ``station_m`` is only filled when a constant speed is supplied: it converts the
    detected time into a station so the event can be tied to the model's geometry.
    """

    from scipy.signal import find_peaks

    series = np.asarray(values, float)
    stamps = np.asarray(time_s, float)
    if series.shape != stamps.shape or series.size < 3:
        raise ChannelContractError("event detection needs two aligned series of length >= 3")
    if not np.all(np.isfinite(series)):
        raise ChannelContractError("event detection input contains non-finite values")
    probe = -series if direction == "minimum" else series
    kwargs: dict[str, float] = {}
    if prominence is not None:
        kwargs["prominence"] = float(prominence)
    if minimum is not None:
        kwargs["height"] = float(minimum) if direction == "maximum" else -float(minimum)
    peaks, _ = find_peaks(probe, **kwargs)
    if peaks.size == 0:
        raise ChannelContractError("no event found with the given thresholds")
    index = int(peaks[int(np.argmax(probe[peaks]))])
    station = None if speed_m_s is None else station_at_zero_m + speed_m_s * float(stamps[index])
    return DetectedEvent(float(stamps[index]), station, channel, float(series[index]), index)


def observed_from_measured(time_s: np.ndarray, columns: dict[str, np.ndarray], *,
                           plan: SensorPlan, role: str = "data") -> ObservationSet:
    """Assemble an :class:`ObservationSet` from measured columns using the plan.

    Every requested channel must be present; a missing sensor is an error, not a silent
    omission, because a residual computed over fewer channels than planned would compare
    a different experiment.
    """

    wanted = [channel for channel in plan if channel.role == role]
    if not wanted:
        raise ChannelContractError(f"the plan has no channels with role {role!r}")
    missing = [channel.name for channel in wanted if channel.name not in columns]
    if missing:
        raise ChannelContractError(f"measured data lacks: {', '.join(missing)}")
    rows = [np.asarray(columns[channel.name], float) for channel in wanted]
    length = rows[0].shape[0]
    if any(row.shape[0] != length for row in rows):
        raise ChannelContractError("measured channels have different lengths")
    if np.asarray(time_s).shape[0] != length:
        raise ChannelContractError("time vector length disagrees with the channels")
    return ObservationSet(tuple(channel.spec() for channel in wanted),
                          np.asarray(time_s, float), np.array(rows, float), "s",
                          {"source": "measured", "sensors": str(len(wanted))})


__all__ = [
    "ChannelContractError",
    "DetectedEvent",
    "SensorChannel",
    "SensorPlan",
    "StrainCalibration",
    "detect_peak_event",
    "force_from_moment",
    "influence_ordinate_simple_support",
    "moment_from_strain",
    "observed_from_measured",
    "standard_turnout_plan",
    "strain_channel_to_force",
]
