"""Measurement-like observables derived from a Velch history.

The point is to compare *what a sensor would have recorded*, not the state variable that is
easiest to print.  Two structural limits are stated up front because they decide how far a
comparison can legitimately be pushed:

* the 35-DOF vehicle has no axle-box body, so an "axle-box acceleration" computed here is the
  wheelset's own acceleration.  A real axle-box accelerometer is mounted above the bearing and
  carries the box/bearing local dynamics on top of it, so this value is a *lower bound* on what
  such an accelerometer would read, not a substitute;
* the rail carries one lumped vertical degree of freedom per rail, not one per sleeper bay, so
  "rail acceleration at a station" is only defined as that lumped quantity until the rail is
  discretised (``track_dynamics = local_compliant``/``layered`` both keep one node per rail).

Both limits are properties of the current model; the functions below stay correct and get sharper
when the model gains axle boxes and a discretised rail.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from ..io.history import HistoryError, HistoryTable


class SensorModelError(ValueError):
    """Raised when a history cannot supply the channel a sensor needs."""


@dataclass(frozen=True)
class SensorTrace:
    """One measurement-like series, ready to go through :mod:`velch.inverse.bands`."""

    name: str
    unit: str
    time_s: np.ndarray
    values: np.ndarray
    note: str = ""

    @property
    def rate_hz(self) -> float:
        if self.time_s.size < 2:
            return float("nan")
        return float(1.0 / np.median(np.diff(self.time_s)))

    def __len__(self) -> int:
        return int(self.time_s.size)


def differentiate(time_s: Sequence[float], values: Sequence[float], order: int = 2) -> np.ndarray:
    """Derivative on a possibly non-uniform time axis (central differences).

    ``order`` 1 gives velocity, 2 gives acceleration, 0 returns the input as an array.
    """
    t = np.asarray(time_s, dtype=float)
    x = np.asarray(values, dtype=float)
    if t.ndim != 1 or x.ndim != 1 or t.size != x.size:
        raise SensorModelError("time and values must be 1-D and of equal length")
    if t.size < order + 2:
        raise SensorModelError(f"need at least {order + 2} samples for order {order}")
    if not np.all(np.isfinite(t)) or not np.all(np.isfinite(x)):
        raise SensorModelError("differentiate received non-finite input")
    if np.any(np.diff(t) <= 0.0):
        raise SensorModelError("time axis must be strictly increasing")
    result = x.copy()
    for _ in range(order):
        result = np.gradient(result, t)
    return result


def _channel(history: HistoryTable, name: str) -> np.ndarray:
    try:
        return history[name]
    except HistoryError as exc:  # pragma: no cover - message detail only
        raise SensorModelError(str(exc)) from exc


def wheelset_acceleration(history: HistoryTable, axle: int) -> SensorTrace:
    """Wheelset vertical acceleration, the lower bound of an axle-box reading."""
    prefix = f"axle{int(axle)}"
    values = differentiate(history.time_s, _channel(history, f"{prefix}_z_m"))
    return SensorTrace(
        name=f"axle{int(axle)}_wheelset_acceleration_z",
        unit="m/s^2",
        time_s=np.asarray(history.time_s, dtype=float),
        values=values,
        note="wheelset DOF, no axle-box body: lower bound on an axle-box accelerometer",
    )


def rail_acceleration(history: HistoryTable, axle: int, side: str) -> SensorTrace:
    """Lumped rail vertical acceleration for one side of one axle."""
    if side not in ("left", "right"):
        raise SensorModelError(f"side must be 'left' or 'right', got {side!r}")
    values = differentiate(history.time_s, _channel(history, f"axle{int(axle)}_{side}_z_m"))
    return SensorTrace(
        name=f"axle{int(axle)}_{side}_rail_acceleration_z",
        unit="m/s^2",
        time_s=np.asarray(history.time_s, dtype=float),
        values=values,
        note="lumped rail DOF: not station resolved until the rail is discretised",
    )


def rail_displacement(history: HistoryTable, axle: int, side: str) -> SensorTrace:
    """Rail vertical displacement (the quantity a displacement transducer would record)."""
    if side not in ("left", "right"):
        raise SensorModelError(f"side must be 'left' or 'right', got {side!r}")
    values = _channel(history, f"axle{int(axle)}_{side}_z_m")
    return SensorTrace(
        name=f"axle{int(axle)}_{side}_rail_displacement_z",
        unit="m",
        time_s=np.asarray(history.time_s, dtype=float),
        values=values,
    )


def bending_strain_micro(moment_nm: float, young_pa: float, second_moment_m4: float,
                         fibre_m: float) -> float:
    """Rail-foot bending strain in microstrain from a bending moment.

    ``fibre_m`` is the distance from the neutral axis to the gauge location (rail foot distance).
    """
    if young_pa <= 0 or second_moment_m4 <= 0:
        raise SensorModelError("young modulus and second moment must be positive")
    strain = moment_nm * fibre_m / (young_pa * second_moment_m4)
    return 1e6 * strain


def resample(time_s: Sequence[float], values: Sequence[float], rate_hz: float) -> tuple[np.ndarray, np.ndarray]:
    """Put model output on the measurement sampling rate before applying a band convention."""
    if not math.isfinite(rate_hz) or rate_hz <= 0:
        raise SensorModelError(f"rate_hz must be positive, got {rate_hz!r}")
    t = np.asarray(time_s, dtype=float)
    x = np.asarray(values, dtype=float)
    if t.size < 2:
        raise SensorModelError("need at least two samples to resample")
    step = 1.0 / rate_hz
    count = int(math.floor((t[-1] - t[0]) / step)) + 1
    grid = t[0] + step * np.arange(count, dtype=float)
    return grid, np.interp(grid, t, x)


def sensor_table(history: HistoryTable, *, axles: Iterable[int] = (1, 2, 3, 4),
                 sides: Sequence[str] = ("left", "right")) -> list[SensorTrace]:
    """Every sensor-like trace this history can supply."""
    traces: list[SensorTrace] = []
    for axle in axles:
        prefix = f"axle{int(axle)}"
        if f"{prefix}_z_m" in history:
            traces.append(wheelset_acceleration(history, axle))
        for side in sides:
            if f"{prefix}_{side}_z_m" in history:
                traces.append(rail_acceleration(history, axle, side))
                traces.append(rail_displacement(history, axle, side))
    return traces
