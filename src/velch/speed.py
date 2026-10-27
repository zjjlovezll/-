"""How fast the vehicle is going, as a value rather than a field read in eighteen places.

The solver currently takes one number, ``cfg.travel_speed_m_s``, and uses it for six
different jobs: mileage mapping, the creep reference speed, the centrifugal force, the
attitude, the wheelset spin and the gate bookkeeping.  A run at a real line speed varies
with time, so the question "what is v" has to become a question about *when*.

This module is the data structure only.  It answers ``v_at(t)`` and ``x_at(t)`` for a
constant profile and for a sequence of constant-speed legs, and it deliberately keeps the
constant case a closed form rather than a cumulative sum, so a caller that used to read
``travel_speed_m_s`` can keep producing bit-identical mileage.

What it is not: it does not yet drive the solver.  Wiring it in needs the mileage, creep,
centrifugal and spin sites to ask the schedule instead of the config, and the spin has to
track ``v/r`` or the wheelset reports a fake longitudinal slip -- see
``docs/VEHICLE_SPEED_PROFILE_2026-10-27.md``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


class SpeedScheduleError(ValueError):
    """The schedule asked for cannot be built or evaluated."""


def _speed_from(entry: dict, *, where: str = "constant") -> float:
    """One speed, with its unit named by the key rather than assumed."""

    has_kmh = "speed_kmh" in entry
    has_ms = "speed_m_s" in entry
    if has_kmh == has_ms:
        raise SpeedScheduleError(
            f"{where} needs exactly one of 'speed_kmh' and 'speed_m_s'; got "
            f"speed_kmh={entry.get('speed_kmh')!r}, speed_m_s={entry.get('speed_m_s')!r}")
    if has_kmh:
        return float(entry["speed_kmh"]) / 3.6
    return float(entry["speed_m_s"])


@dataclass(frozen=True)
class Leg:
    """One constant-speed stretch.

    Give exactly one of ``duration_s`` and ``distance_m``: a speed held for a time, or a
    speed held until a distance has been covered.  Both are kept because a driver holds a
    speed for a while and a railway holds a speed over a stretch.
    """

    speed_m_s: float
    duration_s: float | None = None
    distance_m: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.speed_m_s) or self.speed_m_s <= 0.0:
            raise SpeedScheduleError(f"leg speed must be finite and positive; got {self.speed_m_s!r}")
        given = [self.duration_s is not None, self.distance_m is not None]
        if sum(given) != 1:
            raise SpeedScheduleError(
                "a leg needs exactly one of duration_s and distance_m; got "
                f"duration_s={self.duration_s!r}, distance_m={self.distance_m!r}"
            )
        if self.duration_s is not None:
            if not math.isfinite(self.duration_s) or self.duration_s <= 0.0:
                raise SpeedScheduleError(f"leg duration must be finite and positive; got {self.duration_s!r}")
        if self.distance_m is not None:
            if not math.isfinite(self.distance_m) or self.distance_m <= 0.0:
                raise SpeedScheduleError(f"leg distance must be finite and positive; got {self.distance_m!r}")

    @property
    def length_s(self) -> float:
        if self.duration_s is not None:
            return float(self.duration_s)
        return float(self.distance_m) / self.speed_m_s

    @property
    def length_m(self) -> float:
        if self.distance_m is not None:
            return float(self.distance_m)
        return self.speed_m_s * float(self.duration_s)


@dataclass(frozen=True)
class SpeedSchedule:
    """A non-decreasing sequence of constant-speed legs covering ``[0, duration]``."""

    legs: tuple[Leg, ...]

    def __post_init__(self) -> None:
        if not self.legs:
            raise SpeedScheduleError("a speed schedule needs at least one leg")
        starts = [0.0]
        for leg in self.legs:
            starts.append(starts[-1] + leg.length_s)
        total = starts[-1]
        if not total > 0.0:
            raise SpeedScheduleError("the schedule covers no time")
        object.__setattr__(self, "_starts", tuple(starts))
        object.__setattr__(self, "_total_s", total)

    # ---- constructors -------------------------------------------------------------
    @classmethod
    def constant(cls, speed_m_s: float, duration_s: float | None = None) -> "SpeedSchedule":
        """One leg.  ``duration`` is only used to report the length; it does not change v."""

        if duration_s is None:
            duration_s = 1.0
        return cls(legs=(Leg(speed_m_s=speed_m_s, duration_s=duration_s),))

    @classmethod
    def from_legs(cls, legs: list[Leg] | tuple[Leg, ...]) -> "SpeedSchedule":
        return cls(legs=tuple(legs))

    @classmethod
    def from_spec(cls, spec: "dict") -> "SpeedSchedule":
        """Read the ``run.speed_profile`` block.

        Two shapes, both explicit about units, because a bare number would be read as m/s by
        one author and km/h by the next::

            {"constant": {"speed_kmh": 80.0}}
            {"legs": [{"speed_kmh": 80.0, "duration_s": 2.0},
                      {"speed_m_s": 30.0, "distance_m": 120.0}]}
        """
        if not isinstance(spec, dict):
            raise SpeedScheduleError("'speed_profile' must be an object")
        unknown = set(spec) - {"constant", "legs"}
        if unknown:
            raise SpeedScheduleError(
                f"unknown speed_profile keys {sorted(unknown)}; use 'constant' or 'legs'")
        if ("constant" in spec) == ("legs" in spec):
            raise SpeedScheduleError("speed_profile needs exactly one of 'constant' and 'legs'")
        if "constant" in spec:
            entry = spec["constant"]
            if not isinstance(entry, dict):
                raise SpeedScheduleError("'constant' must be an object with a speed")
            speed = _speed_from(entry)
            duration = entry.get("duration_s")
            return cls.constant(speed, duration_s=None if duration is None else float(duration))
        legs_raw = spec["legs"]
        if not isinstance(legs_raw, (list, tuple)) or not legs_raw:
            raise SpeedScheduleError("'legs' must be a non-empty list")
        legs = []
        for index, entry in enumerate(legs_raw):
            if not isinstance(entry, dict):
                raise SpeedScheduleError(f"leg {index} must be an object")
            speed = _speed_from(entry, where=f"leg {index}")
            duration = entry.get("duration_s")
            distance = entry.get("distance_m")
            unknown_leg = set(entry) - {"speed_kmh", "speed_m_s", "duration_s", "distance_m"}
            if unknown_leg:
                raise SpeedScheduleError(f"leg {index} has unknown keys {sorted(unknown_leg)}")
            legs.append(Leg(
                speed_m_s=speed,
                duration_s=None if duration is None else float(duration),
                distance_m=None if distance is None else float(distance),
            ))
        return cls(legs=tuple(legs))

    # ---- properties ---------------------------------------------------------------
    @property
    def starts_s(self) -> tuple[float, ...]:
        return getattr(self, "_starts")

    @property
    def leg_end_times_s(self) -> tuple[float, ...]:
        """Cumulative end time of every leg, i.e. the instants the schedule may jump."""

        total = 0.0
        ends: list[float] = []
        for leg in self.legs:
            total += leg.length_s
            ends.append(total)
        return tuple(ends)

    @property
    def duration_s(self) -> float:
        return getattr(self, "_total_s")

    @property
    def distance_m(self) -> float:
        return sum(leg.length_m for leg in self.legs)

    @property
    def speeds(self) -> tuple[float, ...]:
        return tuple(leg.speed_m_s for leg in self.legs)

    @property
    def min_speed_m_s(self) -> float:
        return min(self.speeds)

    @property
    def max_speed_m_s(self) -> float:
        return max(self.speeds)

    @property
    def is_constant(self) -> bool:
        first = self.legs[0].speed_m_s
        return all(abs(leg.speed_m_s - first) <= 1e-12 * max(1.0, abs(first))
                   for leg in self.legs[1:])

    @property
    def constant_speed_m_s(self) -> float:
        if not self.is_constant:
            raise SpeedScheduleError(
                f"the schedule is not constant: speeds {self.speeds}; ask v_at(t) instead"
            )
        return self.legs[0].speed_m_s

    # ---- evaluation ---------------------------------------------------------------
    def v_at(self, t_s: float) -> float:
        if not math.isfinite(t_s):
            raise SpeedScheduleError(f"time must be finite; got {t_s!r}")
        if t_s < 0.0:
            raise SpeedScheduleError(f"time must not be negative; got {t_s!r}")
        if self.is_constant:
            return self.legs[0].speed_m_s
        starts = self.starts_s
        for index, leg in enumerate(self.legs):
            if t_s < starts[index + 1] or index == len(self.legs) - 1:
                return leg.speed_m_s
        raise SpeedScheduleError("unreachable")  # pragma: no cover

    def x_at(self, t_s: float, *, x_start_m: float = 0.0) -> float:
        """Distance covered by ``t_s``.

        The constant case is the closed form ``x_start + v t`` on purpose: it is the one
        every existing case uses, and a cumulative sum would change the last bits of the
        mileage, which changes every sampled profile station.
        """
        if not math.isfinite(t_s) or t_s < 0.0:
            raise SpeedScheduleError(f"time must be finite and non-negative; got {t_s!r}")
        if self.is_constant:
            return float(x_start_m) + self.legs[0].speed_m_s * t_s
        starts = self.starts_s
        covered = 0.0
        for index, leg in enumerate(self.legs):
            begin = starts[index]
            if t_s <= begin:
                break
            span = min(t_s, starts[index + 1]) - begin
            covered += leg.speed_m_s * span
        return float(x_start_m) + covered

    def describe(self) -> str:
        if self.is_constant:
            return f"constant {self.legs[0].speed_m_s:.4f} m/s over {self.duration_s:.3f} s"
        pieces = ", ".join(
            f"{leg.speed_m_s:.3f} m/s for {leg.length_s:.3f} s" for leg in self.legs
        )
        return f"{len(self.legs)} legs: {pieces} ({self.distance_m:.2f} m total)"
