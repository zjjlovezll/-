"""The vehicle's lateral path along the line: straight, or the diverging route of a turnout.

Why a separate object rather than a case field with two floats: a diverging route is a *function* of
station (the centerline leaves the through route and returns to straight beyond the frog), so both the
wheel's lateral offset and its lateral velocity (which feeds creepage) must be evaluated per axle
position.  Keeping it a frozen value object with its own validation means the schema stays honest:
either there is no path (straight) or there is a monotone station table that the solver can trust.

Coordinate convention (same as the rest of Velch): +y points to the right of the direction of travel,
the through route's centerline is y = 0, and a positive path value means the vehicle has moved to the
right of the through route's centerline -- which is what a right-hand diverging route does.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class PathError(ValueError):
    """The path table is not usable."""


@dataclass(frozen=True)
class PathTrack:
    """Piecewise-linear lateral path of the vehicle, in metres, indexed by station."""

    stations_s_m: tuple[float, ...]
    y_m: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.stations_s_m) < 2:
            raise PathError("path needs at least two stations")
        if len(self.stations_s_m) != len(self.y_m):
            raise PathError("path stations and offsets must have equal length")
        stations = np.asarray(self.stations_s_m, dtype=float)
        offsets = np.asarray(self.y_m, dtype=float)
        if not np.all(np.isfinite(stations)) or not np.all(np.isfinite(offsets)):
            raise PathError("path table contains non-finite values")
        if np.any(np.diff(stations) <= 0.0):
            raise PathError("path stations must be strictly increasing")

    # -- evaluation ---------------------------------------------------------------------------
    def at(self, station_m: float) -> float:
        """Lateral offset of the vehicle's centerline at a station (0 outside the table)."""
        station = float(station_m)
        if station <= self.stations_s_m[0]:
            return self.y_m[0] if station >= self.stations_s_m[0] else 0.0
        if station >= self.stations_s_m[-1]:
            return self.y_m[-1] if station <= self.stations_s_m[-1] else 0.0
        return float(np.interp(station, self.stations_s_m, self.y_m))

    def slope_at(self, station_m: float) -> float:
        """d(lateral offset)/d(station) -- dimensionless; zero outside the table."""
        station = float(station_m)
        if station <= self.stations_s_m[0] or station >= self.stations_s_m[-1]:
            return 0.0
        stations = np.asarray(self.stations_s_m, dtype=float)
        index = int(np.searchsorted(stations, station, side="right") - 1)
        index = min(max(index, 0), len(stations) - 2)
        span = stations[index + 1] - stations[index]
        return float((self.y_m[index + 1] - self.y_m[index]) / span)

    def lateral_velocity_m_s(self, station_m: float, speed_m_s: float) -> float:
        """Rate at which the wheel surface moves laterally in the rail frame."""
        return float(speed_m_s) * self.slope_at(station_m)

    @property
    def span_m(self) -> tuple[float, float]:
        return (self.stations_s_m[0], self.stations_s_m[-1])

    def summary(self) -> str:
        return (f"path {self.span_m[0]:.3f}..{self.span_m[1]:.3f} m, "
                f"offset {min(self.y_m) * 1e3:+.1f}..{max(self.y_m) * 1e3:+.1f} mm")


def load_path(raw: object) -> PathTrack | None:
    """Accept ``{"stations_s_m": [...], "y_m": [...]}`` (or a list of pairs) from a case file."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        stations = raw.get("stations_s_m")
        offsets = raw.get("y_m")
        if stations is None or offsets is None:
            raise PathError("path needs 'stations_s_m' and 'y_m'")
        return PathTrack(tuple(float(v) for v in stations), tuple(float(v) for v in offsets))
    if isinstance(raw, list):
        pairs = [(float(p[0]), float(p[1])) for p in raw]
        return PathTrack(tuple(p[0] for p in pairs), tuple(p[1] for p in pairs))
    raise PathError(f"unsupported path specification: {type(raw).__name__}")
