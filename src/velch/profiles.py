"""Versioned graph profiles and longitudinal station selection.

PRR and TXT files are only geometry inputs. No Simpack interpolation semantics
are inferred. Ambiguous coincident stations require explicit branch mapping.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


class ProfileError(ValueError):
    """Invalid or ambiguous profile geometry."""


class AmbiguousProfileError(ProfileError):
    """An unresolved coincident station could change the chosen geometry."""


@dataclass(frozen=True)
class GraphProfile:
    y_m: np.ndarray
    z_m: np.ndarray
    source_sha256: str
    source: str
    collapsed_points: int = 0
    _node_spacing_m: float | None = field(default=None, repr=False, compare=False)
    # Interpolated samples inherit an ascending node grid by construction, so the
    # O(n) monotonicity/finiteness sweep is skipped for them; it cost about a fifth
    # of a dynamics evaluation when it ran on every sample.
    verified: bool = field(default=True, repr=False, compare=False)

    def __post_init__(self) -> None:
        y = np.asarray(self.y_m, dtype=float)
        z = np.asarray(self.z_m, dtype=float)
        if y.ndim != 1 or z.ndim != 1 or len(y) != len(z) or len(y) < 3:
            raise ProfileError("profile must have at least three paired y,z points")
        if self.verified:
            if not np.all(np.isfinite(y)) or not np.all(np.isfinite(z)):
                raise ProfileError("profile has non-finite coordinates")
            if not np.all(np.diff(y) > 0):
                raise ProfileError("profile y coordinates must increase strictly")
        if not self.source_sha256:
            raise ProfileError("profile content identity is required")
        y.setflags(write=False)
        z.setflags(write=False)
        object.__setattr__(self, "y_m", y)
        object.__setattr__(self, "z_m", z)

    def z_at(self, y_m: np.ndarray | float) -> np.ndarray:
        query = np.asarray(y_m, dtype=float)
        if np.any(query < self.y_m[0]) or np.any(query > self.y_m[-1]):
            raise ProfileError("lateral profile query outside the measured envelope")
        return np.interp(query, self.y_m, self.z_m)

    @property
    def node_spacing_m(self) -> float:
        """Median lateral spacing between nodes, computed once per profile.

        The contact law sizes its curvature window from this spacing, and computing
        it by ``np.median(np.diff(y))`` on every evaluation sorted a two-thousand
        point array sixteen times per right-hand side.  It is a property of the
        frozen geometry, so it is memoised on first use.
        """
        cached = self._node_spacing_m
        if cached is None:
            cached = float(np.median(np.diff(self.y_m))) if self.y_m.size > 1 else 0.0
            object.__setattr__(self, "_node_spacing_m", cached)
        return cached


def graph_from_points(
    points: np.ndarray,
    *,
    source_sha256: str,
    source: str,
    surface: str,
    y_scale_m: float = 1.0,
    z_scale_m: float = 1.0,
    y_sign: int = 1,
    z_sign: int = 1,
    y_offset_m: float = 0.0,
    z_offset_m: float = 0.0,
    roll_rad: float = 0.0,
    roll_pivot_y_m: float = 0.0,
    roll_pivot_z_m: float = 0.0,
) -> GraphProfile:
    """Collapse a potentially multivalued profile to an explicit graph envelope.

    `rail_top` retains the highest z at repeated y; `wheel_lower` retains the
    lowest. This is a modelling choice, not a claim about Simpack contact search.

    `roll_rad` rotates the profile *after* the sign/scale/offset transform, about
    the point `(roll_pivot_y_m, roll_pivot_z_m)` in the final frame. That is how
    rail cant (轨底坡, e.g. 1:40) is represented: the running surface tilts while
    the crown centre keeps its design height. Rotating about the gauge face
    instead would raise the crown by `half_width * tan(cant)` — 0.9 mm at 1:40 —
    which is a dimensional error, not a small perturbation.
    """
    raw = np.asarray(points, dtype=float)
    if raw.ndim != 2 or raw.shape[1] != 2 or raw.shape[0] < 3:
        raise ProfileError("expected an N by 2 point array")
    if surface not in {"rail_top", "wheel_lower"}:
        raise ProfileError("surface must be rail_top or wheel_lower")
    for value in (y_scale_m, z_scale_m):
        if not math.isfinite(value) or value <= 0:
            raise ProfileError("coordinate scales must be finite and positive")
    if y_sign not in {-1, 1} or z_sign not in {-1, 1}:
        raise ProfileError("coordinate signs must be -1 or +1")
    if not np.all(np.isfinite(raw)) or not all(math.isfinite(v) for v in
                                               (y_offset_m, z_offset_m, roll_rad,
                                                roll_pivot_y_m, roll_pivot_z_m)):
        raise ProfileError("non-finite profile coordinate or offset")
    y = raw[:, 0] * y_scale_m * y_sign + y_offset_m
    z = raw[:, 1] * z_scale_m * z_sign + z_offset_m
    if roll_rad:
        dy = y - roll_pivot_y_m
        dz = z - roll_pivot_z_m
        cosine, sine = math.cos(roll_rad), math.sin(roll_rad)
        y = roll_pivot_y_m + cosine * dy - sine * dz
        z = roll_pivot_z_m + sine * dy + cosine * dz
    order = np.argsort(y, kind="stable")
    y, z = y[order], z[order]
    unique, first, counts = np.unique(y, return_index=True, return_counts=True)
    reducer = np.maximum.reduceat if surface == "rail_top" else np.minimum.reduceat
    envelope = reducer(z, first)
    return GraphProfile(unique, envelope, source_sha256, source, int(len(y) - len(unique)))


def load_profile(path: Path, *, file_format: str, surface: str, **transform: float | int) -> GraphProfile:
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if file_format in {"txt", "csv"}:
        separator = "," if file_format == "csv" else None
        try:
            points = np.loadtxt(path, delimiter=separator, usecols=(0, 1), comments="#")
        except (OSError, ValueError) as exc:
            raise ProfileError(f"cannot parse two-column {file_format}: {path}") from exc
    elif file_format == "prr":
        if len(data) > 16 * 1024 * 1024:
            raise ProfileError("PRR exceeds 16 MiB inspection bound")
        text = data.decode("utf-8", errors="replace")
        unit = re.search(r"^\s*units\.len\s*=\s*['\"]([^'\"]+)", text, re.MULTILINE)
        if unit is None or unit.group(1) != "m":
            raise ProfileError("PRR length unit must explicitly be m")
        profile_type = re.search(r"^\s*type\s*=\s*([01])\b", text, re.MULTILINE)
        expected_type = "0" if surface == "rail_top" else "1"
        if profile_type is None or profile_type.group(1) != expected_type:
            raise ProfileError(f"PRR type must be {expected_type} for {surface}")
        start = text.find("point.begin")
        end = text.find("point.end", start + len("point.begin"))
        if start < 0 or end < 0:
            raise ProfileError("PRR point block is missing")
        rows = []
        for line in text[start + len("point.begin"):end].splitlines():
            line = line.strip()
            if not line or line.startswith("!"):
                continue
            fields = line.split()
            if len(fields) < 2:
                raise ProfileError("invalid PRR point row")
            try:
                rows.append((float(fields[0]), float(fields[1])))
            except ValueError as exc:
                raise ProfileError("invalid PRR numeric point") from exc
        points = np.asarray(rows, dtype=float)
    else:
        raise ProfileError("format must be txt, csv, or prr")
    return graph_from_points(points, source_sha256=digest, source=str(path), surface=surface, **transform)


@dataclass(frozen=True)
class Station:
    s_m: float
    profile: GraphProfile
    profile_id: str

    def __post_init__(self) -> None:
        if not math.isfinite(self.s_m) or not self.profile_id:
            raise ProfileError("station and profile ID must be finite and nonempty")


@dataclass(frozen=True)
class ProfileSample:
    profile: GraphProfile
    dz_ds: np.ndarray
    lower_s_m: float
    upper_s_m: float
    selected_ids: tuple[str, ...]


class ProfileSeries:
    def __init__(self, stations: list[Station], branches: dict[str, dict[str, str]] | None = None):
        if not stations:
            raise ProfileError("profile series is empty")
        grouped: dict[float, list[Station]] = {}
        for item in stations:
            grouped.setdefault(item.s_m, []).append(item)
        self._stations = sorted(grouped)
        # np.searchsorted on a Python list of stations re-converts to an array on
        # every sample, which showed up as a measurable cost inside a dynamics
        # evaluation; the array form is searched directly and gives the same
        # insertion indices.
        self._station_index = np.asarray(self._stations, dtype=float)
        self._groups = grouped
        self._branches = branches or {}
        self._interval_cache: dict[int, tuple] = {}
        for s, group in grouped.items():
            if len({item.profile_id for item in group}) != len(group):
                raise ProfileError(f"duplicate profile ID at {s} m")
            if len({item.profile.source_sha256 for item in group}) > 1:
                selection = self._branches.get(str(s))
                if not selection or set(selection) != {"before", "after"}:
                    # Construction is allowed for inspection; sampling will refuse.
                    continue
                if any(selection[side] not in {item.profile_id for item in group} for side in ("before", "after")):
                    raise ProfileError(f"unknown branch profile at {s} m")

    def covers(self, s_m: float) -> bool:
        # True when the station range brackets this mileage.
        return bool(self._station_index[0] <= s_m <= self._station_index[-1])

    @property
    def lowest_m(self) -> float:
        """First station mileage.  Readers that sweep the surface need these bounds."""
        return float(self._station_index[0])

    @property
    def highest_m(self) -> float:
        """Last station mileage."""
        return float(self._station_index[-1])

    def mileages(self) -> tuple[float, ...]:
        """Every station mileage, ascending (duplicates collapsed by construction)."""
        return tuple(self._stations)

    def _select(self, s: float, side: str) -> Station:
        group = self._groups[s]
        if len({item.profile.source_sha256 for item in group}) == 1:
            return group[0]
        selection = self._branches.get(str(s))
        if not selection:
            raise AmbiguousProfileError(f"{s} m has distinct profiles; configure before/after")
        return next(item for item in group if item.profile_id == selection[side])

    def sample(self, s_m: float, direction: int = 1) -> ProfileSample:
        if not math.isfinite(s_m) or direction not in {-1, 1}:
            raise ProfileError("station must be finite and direction must be -1 or +1")
        stations = self._stations
        if s_m < stations[0] - 1e-10 or s_m > stations[-1] + 1e-10:
            raise ProfileError(f"station {s_m} m outside [{stations[0]}, {stations[-1]}]")
        s_m = min(max(s_m, stations[0]), stations[-1])
        at = int(np.searchsorted(self._station_index, s_m))
        if at < len(stations) and math.isclose(stations[at], s_m, rel_tol=0, abs_tol=1e-10):
            selected = self._select(stations[at], "after" if direction > 0 else "before")
            if len(stations) == 1:
                derivative = np.zeros_like(selected.profile.z_m)
            else:
                neighbor = min(at + 1, len(stations) - 1) if direction > 0 else max(at - 1, 0)
                if neighbor == at:
                    neighbor = max(at - 1, 0) if direction > 0 else min(at + 1, len(stations) - 1)
                if abs(float(stations[neighbor]) - float(stations[at])) <= 1e-12:
                    # A repeated mileage has no direction to difference along: the neighbour is the
                    # same station.  Measured on the turnout table, where this produced
                    # `dz_ds = nan` over 52-74 m and made the seat report four of eight wheels.
                    derivative = np.zeros_like(selected.profile.z_m)
                else:
                    other = self._select(stations[neighbor],
                                         "before" if neighbor > at else "after")
                    derivative = _station_derivative(selected, other)
            return ProfileSample(selected.profile, derivative, stations[at], stations[at], (selected.profile_id,))
        # The interpolation grid, the sampled endpoint shapes and the source
        # digest prefix depend only on the station pair, not on the position
        # inside the interval. Rebuilding them per sample dominated the cost of
        # a dynamics evaluation, so they are memoised per interval; the cached
        # arrays are read-only and never mutated by callers.
        cached = self._interval_cache.get(at)
        if cached is None:
            lower_s, upper_s = stations[at - 1], stations[at]
            lower = self._select(lower_s, "after")
            upper = self._select(upper_s, "before")
            y_min = max(lower.profile.y_m[0], upper.profile.y_m[0])
            y_max = min(lower.profile.y_m[-1], upper.profile.y_m[-1])
            if y_max <= y_min:
                raise ProfileError("adjacent profiles have no lateral overlap")
            y = np.unique(np.concatenate((
                np.array([y_min, y_max]),
                lower.profile.y_m[(lower.profile.y_m > y_min) & (lower.profile.y_m < y_max)],
                upper.profile.y_m[(upper.profile.y_m > y_min) & (upper.profile.y_m < y_max)],
            )))
            y.setflags(write=False)
            z_lower = lower.profile.z_at(y)
            z_upper = upper.profile.z_at(y)
            z_lower.setflags(write=False)
            z_upper.setflags(write=False)
            cached = (y, z_lower, z_upper, float(lower_s), float(upper_s),
                      lower.profile.source_sha256 + upper.profile.source_sha256,
                      f"interpolated:{lower.profile_id}:{upper.profile_id}",
                      (lower.profile_id, upper.profile_id))
            if len(self._interval_cache) >= 64:
                self._interval_cache.clear()
            self._interval_cache[at] = cached
        y, z_lower, z_upper, lower_s, upper_s, digest_prefix, source, profile_ids = cached
        fraction = (s_m - lower_s) / (upper_s - lower_s)
        z = (1 - fraction) * z_lower + fraction * z_upper
        digest = hashlib.sha256((digest_prefix + repr(fraction)).encode()).hexdigest()
        profile = GraphProfile(y, z, digest, source, verified=False)
        span = float(upper_s) - float(lower_s)
        if span > 0.0:
            slope = (z_upper - z_lower) / span
        else:
            # A station table may repeat a mileage (the Simpack turnout table does).
            # Interpolating inside a zero-width interval is 0 / 0, and the NaN slope reaches
            # the contact normal: measured `dz_ds = nan` from 52 m to 74 m on case_table.json,
            # which made the static seat report four of eight wheels carrying load.
            slope = np.zeros_like(z_upper)
        return ProfileSample(profile, slope, lower_s, upper_s, profile_ids)


def _station_derivative(current: Station, other: Station) -> np.ndarray:
    y = current.profile.y_m
    derivative = np.full_like(y, np.nan)
    covered = (y >= other.profile.y_m[0]) & (y <= other.profile.y_m[-1])
    if np.count_nonzero(covered) < 2:
        raise ProfileError("adjacent profiles have insufficient common lateral domain")
    derivative[covered] = ((other.profile.z_at(y[covered]) - current.profile.z_m[covered])
                           / (other.s_m - current.s_m))
    return derivative
