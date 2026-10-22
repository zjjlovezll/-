"""Observation layer: pair predicted and observed channels on a common axis.

Two families of observation must coexist:

* **simulation-to-simulation** (this repo vs Simpack): the physical axis is the
  travelled distance, so channels are compared at the *same station*. Both sides
  carry an ``x`` channel and no event detection is needed.
* **measured** (axle-box acceleration, rail-web strain): no station channel and no
  wheel-rail force is available, so alignment is by a detected **event** (frog nose
  crossing, switch throw, a strain peak) plus speed, and the residual is evaluated
  on a time axis anchored at that event.

The layer only aligns and scores. It never decides which parameters are observable;
that belongs to the identifiability stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal, Mapping, Sequence

import numpy as np

from ..io.history import HistoryTable

AlignmentStrategy = Literal["time", "station", "event"]


class ObservationError(ValueError):
    """Raised when observation channels cannot be paired consistently."""


@dataclass(frozen=True)
class ChannelSpec:
    """One observed quantity.

    ``sigma`` is the one-sigma uncertainty in the channel's own unit; it is what the
    residual is normalised by, so a 0.5 kN force channel and a 0.02 g acceleration
    channel contribute comparably. ``role`` separates channels that enter the
    objective (``data``) from channels only checked afterwards (``check``).
    """

    name: str
    unit: str
    role: Literal["data", "check"] = "data"
    sigma: float = 0.0
    frame: str = "track"
    sample_rate_hz: float | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ObservationError("channel spec needs a name")
        if not self.unit:
            raise ObservationError(f"channel {self.name!r} needs a unit")
        if self.role not in ("data", "check"):
            raise ObservationError(f"channel {self.name!r} has an unknown role")
        if self.sigma < 0:
            raise ObservationError(f"channel {self.name!r} has a negative sigma")

    @property
    def weight(self) -> float:
        return 1.0 / self.sigma if self.sigma > 0 else 1.0


@dataclass(frozen=True)
class ObservationSet:
    """Channels sharing one axis (time or station), plus provenance."""

    channels: tuple[ChannelSpec, ...]
    axis: np.ndarray
    values: np.ndarray
    axis_unit: str
    provenance: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.values.ndim != 2:
            raise ObservationError("observation values must be (n_channel, n_sample)")
        if self.values.shape[0] != len(self.channels):
            raise ObservationError("observation channel count disagrees with values")
        if self.values.shape[1] != self.axis.shape[0]:
            raise ObservationError("observation axis length disagrees with values")
        if self.axis.shape[0] < 2:
            raise ObservationError("observation needs at least two samples")

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(channel.name for channel in self.channels)

    def __contains__(self, name: object) -> bool:
        return name in self.names

    def subset(self, names: Iterable[str]) -> "ObservationSet":
        wanted = tuple(names)
        missing = [n for n in wanted if n not in self]
        if missing:
            raise ObservationError(f"unknown observation channels: {', '.join(missing)}")
        indices = [self.names.index(n) for n in wanted]
        return ObservationSet(tuple(self.channels[i] for i in indices), self.axis,
                              self.values[indices], self.axis_unit, dict(self.provenance))

    def only(self, role: str) -> "ObservationSet":
        return self.subset([c.name for c in self.channels if c.role == role])

    @classmethod
    def from_history(cls, table: HistoryTable, specs: Sequence[ChannelSpec],
                     axis_channel: str = "time_s",
                     provenance: Mapping[str, str] | None = None) -> "ObservationSet":
        """Build observations from a typed history table (simulation side)."""

        rows = []
        for spec in specs:
            if spec.name not in table:
                raise ObservationError(f"history has no channel {spec.name!r}")
            unit = table.channels[spec.name].unit
            if unit != spec.unit:
                raise ObservationError(
                    f"channel {spec.name!r} is {unit} in the table but {spec.unit} in the spec")
            rows.append(table[spec.name])
        axis = table[axis_channel]
        axis_unit = table.channels[axis_channel].unit
        meta = dict(provenance or {})
        meta.setdefault("source", table.source)
        meta.setdefault("schema", table.schema_version)
        return cls(tuple(specs), np.asarray(axis, float), np.array(rows, float),
                   axis_unit, meta)

    @classmethod
    def from_csv(cls, path: str | Path, specs: Sequence[ChannelSpec],
                 axis_column: str = "time_s", axis_unit: str = "s",
                 provenance: Mapping[str, str] | None = None) -> "ObservationSet":
        """Build observations from an arbitrary CSV (measured or derived side).

        Unlike :func:`velch.io.history.read_history` the column names are free: the
        caller names them in ``specs``, which is what a measurement export needs.
        """

        source = Path(path)
        if not source.is_file():
            raise ObservationError(f"observation file not found: {source}")
        raw = np.genfromtxt(source, delimiter=",", names=True, dtype=float,
                            encoding="utf-8-sig")
        if raw is None or raw.dtype.names is None:
            raise ObservationError(f"observation file has no header: {source}")
        available = set(raw.dtype.names)
        missing = [spec.name for spec in specs if spec.name not in available]
        if missing:
            raise ObservationError(f"observation file lacks: {', '.join(missing)}")
        if axis_column not in available:
            raise ObservationError(f"observation file lacks axis {axis_column!r}")
        axis = np.atleast_1d(np.asarray(raw[axis_column], float))
        if axis.shape[0] != np.atleast_1d(np.asarray(raw[specs[0].name], float)).shape[0]:
            raise ObservationError("observation columns have different lengths")
        rows = [np.atleast_1d(np.asarray(raw[spec.name], float)) for spec in specs]
        meta = dict(provenance or {})
        meta.setdefault("source", str(source))
        return cls(tuple(specs), axis, np.array(rows, float), axis_unit, meta)


@dataclass(frozen=True)
class Alignment:
    """A paired residual on one axis."""

    axis: np.ndarray
    axis_unit: str
    observed: ObservationSet
    predicted: np.ndarray
    mask: np.ndarray
    channel_metrics: Mapping[str, Mapping[str, float]]
    strategy: AlignmentStrategy

    @property
    def samples(self) -> int:
        return int(np.count_nonzero(self.mask))

    @property
    def residual(self) -> np.ndarray:
        return self.predicted - self.observed.values

    @property
    def rms(self) -> float:
        """Weighted RMS over the overlap, normalised by each channel's sigma."""

        weights = np.array([c.weight for c in self.observed.channels])[:, None]
        piece = self.residual[:, self.mask] * weights
        return float(np.sqrt(np.mean(piece ** 2))) if piece.size else float("nan")

    def summary(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "axis_unit": self.axis_unit,
            "samples": self.samples,
            "channels": list(self.observed.names),
            "rms": self.rms,
            "channel_metrics": {k: dict(v) for k, v in self.channel_metrics.items()},
        }


def _monotonic(axis: np.ndarray, name: str) -> np.ndarray:
    if axis.shape[0] < 2:
        raise ObservationError(f"{name} axis needs two samples")
    if np.all(np.diff(axis) > 0):
        return axis
    if np.all(np.diff(axis) < 0):
        return axis[::-1]
    raise ObservationError(f"{name} axis is not monotonic")


def _resample(source_axis: np.ndarray, values: np.ndarray,
              target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Linear interpolation with a strict overlap mask (no extrapolation)."""

    order = np.argsort(source_axis)
    axis = source_axis[order]
    ordered = values[:, order]
    lower, upper = float(axis[0]), float(axis[-1])
    mask = (target >= lower) & (target <= upper)
    out = np.empty((values.shape[0], target.shape[0]), dtype=float)
    for row in range(values.shape[0]):
        out[row] = np.interp(target, axis, ordered[row])
    return out, mask


def _channel_metrics(observed: ObservationSet, predicted: np.ndarray,
                     mask: np.ndarray) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    for index, spec in enumerate(observed.channels):
        obs = observed.values[index][mask]
        pred = predicted[index][mask]
        if obs.size == 0:
            metrics[spec.name] = {"samples": 0.0}
            continue
        delta = pred - obs
        obs_peak = float(np.max(np.abs(obs)))
        pred_peak = float(np.max(np.abs(pred)))
        metrics[spec.name] = {
            "samples": float(obs.size),
            "rms": float(np.sqrt(np.mean(delta ** 2))),
            "max_abs": float(np.max(np.abs(delta))),
            "observed_peak": obs_peak,
            "predicted_peak": pred_peak,
            "peak_ratio": pred_peak / obs_peak if obs_peak > 0 else float("nan"),
        }
    return metrics


def align(predicted: ObservationSet, observed: ObservationSet,
          strategy: AlignmentStrategy = "time", *,
          station_channel: str = "axle1_x_m",
          event_time_s: float | None = None,
          event_anchor_s: float | None = None,
          samples: int | None = None) -> Alignment:
    """Pair ``predicted`` with ``observed`` on the axis the strategy implies.

    * ``time``    — interpolate the predicted series onto the observed time stamps
                    restricted to the overlap.
    * ``station`` — both sides carry ``station_channel``; pair at equal station. Used
                    for simulation-to-simulation comparison.
    * ``event``   — shift the predicted time axis so ``event_anchor_s`` (predicted)
                    lands on ``event_time_s`` (observed), then align in time. Used for
                    measured data, where no station channel exists.
    """

    if observed.names != predicted.names:
        raise ObservationError(
            "channel sets differ: " + ", ".join(sorted(set(observed.names) ^ set(predicted.names))))
    for name in observed.names:
        left = next(c for c in observed.channels if c.name == name)
        right = next(c for c in predicted.channels if c.name == name)
        if left.unit != right.unit:
            raise ObservationError(f"channel {name!r}: {left.unit} vs {right.unit}")

    if strategy == "station":
        if station_channel not in observed or station_channel not in predicted:
            raise ObservationError(f"station strategy needs {station_channel!r} on both sides")
        obs_station = _monotonic(
            np.asarray(observed.values[observed.names.index(station_channel)], float),
            "observed station")
        pred_station = _monotonic(
            np.asarray(predicted.values[predicted.names.index(station_channel)], float),
            "predicted station")
        order_obs = np.argsort(obs_station)
        order_pred = np.argsort(pred_station)
        obs_station = obs_station[order_obs]
        pred_station = pred_station[order_pred]
        # The common grid is the observed station stamps inside the predicted span;
        # nothing is extrapolated, so a shorter prediction simply yields fewer pairs.
        mask_pred = (obs_station >= pred_station[0]) & (obs_station <= pred_station[-1])
        grid = obs_station[mask_pred]
        if grid.shape[0] < 2:
            raise ObservationError("station ranges overlap in fewer than two samples")
        pred_on_grid, _ = _resample(pred_station, predicted.values[:, order_pred], grid)
        obs_on_grid, _ = _resample(obs_station, observed.values[:, order_obs], grid)
        mask = np.ones(grid.shape, dtype=bool)
        predicted_out = pred_on_grid
        observed_out = ObservationSet(observed.channels, grid, obs_on_grid,
                                      "m", dict(observed.provenance))
        axis = grid
        axis_unit = "m"
    elif strategy in ("time", "event"):
        pred_axis = np.asarray(predicted.axis, float)
        if strategy == "event":
            if event_time_s is None or event_anchor_s is None:
                raise ObservationError("event strategy needs event_time_s and event_anchor_s")
            shift = float(event_anchor_s) - float(event_time_s)
            pred_axis = pred_axis - shift
        elif event_time_s is not None or event_anchor_s is not None:
            raise ObservationError("event arguments given for a time alignment")
        target = _monotonic(np.asarray(observed.axis, float), "observed")
        obs_values = np.asarray(observed.values, float)
        if samples is not None:
            if samples < 2:
                raise ObservationError("samples must be at least two")
            target = np.linspace(float(target[0]), float(target[-1]), samples)
            order_obs = np.argsort(np.asarray(observed.axis, float))
            obs_values, _ = _resample(np.asarray(observed.axis, float)[order_obs],
                                      obs_values[:, order_obs], target)
        pred_on_grid, mask = _resample(pred_axis, predicted.values, target)
        observed_out = ObservationSet(observed.channels, target, obs_values,
                                      observed.axis_unit, dict(observed.provenance))
        predicted_out = pred_on_grid
        axis = target
        axis_unit = observed.axis_unit
    else:
        raise ObservationError(f"unknown alignment strategy {strategy!r}")

    return Alignment(axis, axis_unit, observed_out, predicted_out, mask,
                     _channel_metrics(observed_out, predicted_out, mask), strategy)


def make_spec(name: str, unit: str, **kwargs) -> ChannelSpec:
    return ChannelSpec(name=name, unit=unit, **kwargs)


__all__ = [
    "Alignment",
    "AlignmentStrategy",
    "ChannelSpec",
    "ObservationError",
    "ObservationSet",
    "align",
    "make_spec",
]
