"""Measurement-like observables derived from a Velch history.

The point is to compare *what a sensor would have recorded*, not the state variable that is
easiest to print.  Two structural limits are stated up front because they decide how far a
comparison can legitimately be pushed:

* a vehicle without axle-box bodies (``CRH380A_M``, ``CRH380A_M_node``, ``CRH380A_M_6dof``) has no
  box, so an "axle-box acceleration" for those vehicles is the wheelset's own acceleration.  A real
  axle-box accelerometer is mounted above the bearing and carries the box/bearing local dynamics on
  top of it, so for *those* vehicles the value is a *lower bound*, not a substitute.  A vehicle with
  boxes (``CRH380A_M_axlebox``, eight 48.2 kg bodies) is read directly through
  :func:`axle_box_acceleration`, and then the caveat does not apply -- the box is solved and its
  translational accelerations are written analytically by the solver;
* the rail carries one lumped vertical degree of freedom per rail, not one per sleeper bay, so
  "rail acceleration at a station" is only defined as that lumped quantity until the rail is
  discretised (``track_dynamics = local_compliant``/``layered`` both keep one node per rail).

Note the direction of the axle-box channel, because it is not the obvious one: S7 measured that the
**lateral** box acceleration is the only extra channel that adds a direction the vertical ones cannot
see (novelty 0.374 against seven vertical channels, whose seven rows span only 4 directions).  So the
``axis`` argument is not decoration -- ``"z"`` and ``"y"`` are different sensors with different
information content, and both are offered here.
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
        note="wheelset DOF: a lower bound on an axle-box accelerometer "
             "(use axle_box_acceleration on a vehicle that has boxes)",
    )


#: translation axis -> the suffix the solver writes for its analytic acceleration
_ACCELERATION_AXIS = {"x": "x_acc_m_per_s2", "y": "y_acc_m_per_s2", "z": "z_acc_m_per_s2"}


def axle_box_acceleration(history: HistoryTable, axle: int, side: str,
                          axis: str = "z") -> SensorTrace:
    """Axle-box acceleration **as the solver recorded it**, not as a difference of positions.

    The solver writes each box's translational accelerations analytically (``force / mass`` in the
    same evaluation that the numerical gates use), so nothing is differentiated here.  That matters:
    a second difference of the position channel is a smoothing filter that hides exactly the
    high-frequency content a box accelerometer is deployed to see.

    ``axis`` is ``"x"``, ``"y"`` or ``"z"``.  ``"y"`` is the one S7 found worth installing -- the
    vertical channels alone span only four of twelve measurable directions, and the lateral box
    acceleration is what adds a fifth.  Rotation (``roll``/``pitch``/``yaw``) is deliberately not
    accepted here: those channels carry ``rad/s^2`` and a different unit, so they belong to a caller
    that can hold an angular quantity rather than under a ``m/s^2`` trace.

    A vehicle without axle-box bodies has no such channel; the error says which column was missing
    and which function to use instead, rather than silently differentiating the wheelset.
    """
    if side not in ("left", "right"):
        raise SensorModelError(f"side must be 'left' or 'right', got {side!r}")
    if axis not in _ACCELERATION_AXIS:
        raise SensorModelError(
            f"axis must be one of {sorted(_ACCELERATION_AXIS)}, got {axis!r}"
            " (angular axes carry rad/s^2 and are not offered as translational traces)")
    column = f"axle{int(axle)}_box_{side}_{_ACCELERATION_AXIS[axis]}"
    try:
        values = _channel(history, column)
    except SensorModelError as exc:
        raise SensorModelError(
            f"{exc}; this history has no axle-box channel {column!r}.  Only a vehicle with axle-box "
            "bodies emits it (e.g. vehicle_ref CRH380A_M_axlebox); for a wheelset-only vehicle use "
            "wheelset_acceleration instead") from exc
    return SensorTrace(
        name=f"axle{int(axle)}_box_{side}_acceleration_{axis}",
        unit="m/s^2",
        time_s=np.asarray(history.time_s, dtype=float),
        values=values,
        note="analytic solver output (force/mass); not a differentiated position",
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
    """Every sensor-like trace this history can supply.

    Axle-box traces are offered for all three translation axes that the history actually carries.
    A wheelset-only history yields none of them, and its wheelset acceleration is added instead --
    the two are never both claimed for the same axle, because the box *is* the thing an accelerometer
    is bolted to and reading the wheelset as well would double-count one measurement.
    """
    traces: list[SensorTrace] = []
    for axle in axles:
        prefix = f"axle{int(axle)}"
        boxes: list[str] = []
        for side in sides:
            for axis in _ACCELERATION_AXIS:
                if f"{prefix}_box_{side}_{_ACCELERATION_AXIS[axis]}" in history:
                    traces.append(axle_box_acceleration(history, axle, side, axis))
                    boxes.append(axis)
        if not boxes and f"{prefix}_z_m" in history:
            traces.append(wheelset_acceleration(history, axle))
        for side in sides:
            if f"{prefix}_{side}_z_m" in history:
                traces.append(rail_acceleration(history, axle, side))
                traces.append(rail_displacement(history, axle, side))
    return traces
