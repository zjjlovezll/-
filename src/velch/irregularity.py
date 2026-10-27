"""Track irregularity (Simpack ``.tre`` input functions) for the vehicle–turnout solver.

Simpack does not bend the rail profile to add irregularity: a *track element* carries four
excitation slots (lateral, vertical, roll, gauge), each slot reads one column of an
**input-function file** (``.tre``), and the track element applies the sample at the current
mileage inside a start/end window with a fade.  We mirror exactly that, with one deliberate
difference stated in ``docs/SIMPACK_IRREGULARITY_MINING_2026-10-23.md``: the offsets are applied
to the sampled rail surface instead of to the track centreline reference.

Two file shapes exist in the wild and only one of them is text:

* ASCII — ``header.begin`` … ``header.end`` and then one line per sample.  Simpack reads it and
  the accompanying MATLAB generator writes it.  This module reads and writes this shape.
* binary — what Simpack 2021x saves by default (``\\x00\\x00\\x00\\x08`` header, floats inline).
  We refuse it by name instead of guessing, because a wrong guess here silently changes the
  excitation amplitude.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

#: Column order of ``data.type = 1`` (the only type this module accepts).
CHANNELS = ("lateral", "vertical", "roll", "gauge")

#: Unit factor slots in the header, in the same order as :data:`CHANNELS`.
UNIT_KEYS = ("data.par(2)", "data.par(3)", "data.par(4)", "data.par(5)")

HEADER_BEGIN = "header.begin"
HEADER_END = "header.end"
SUPPORTED_TYPE = 1


class IrregularityError(ValueError):
    """The ``.tre`` file cannot be read, or the request contradicts its contents."""


@dataclass(frozen=True)
class IrregularityTrack:
    """One ``.tre`` data set, in SI units, ready to be sampled at a mileage."""

    s_m: np.ndarray
    lateral_m: np.ndarray
    vertical_m: np.ndarray
    roll_rad: np.ndarray
    gauge_m: np.ndarray
    source: str = ""

    def __post_init__(self) -> None:
        n = len(self.s_m)
        if n < 2:
            raise IrregularityError("an irregularity track needs at least two samples")
        for name in ("lateral_m", "vertical_m", "roll_rad", "gauge_m"):
            if len(getattr(self, name)) != n:
                raise IrregularityError(f"{name} has {len(getattr(self, name))} values, s_m has {n}")
        if not np.all(np.isfinite(self.s_m)):
            raise IrregularityError("irregularity mileage contains non-finite values")
        if np.any(np.diff(self.s_m) <= 0.0):
            raise IrregularityError("irregularity mileage must increase strictly")

    def __len__(self) -> int:
        return int(len(self.s_m))

    @property
    def span_m(self) -> tuple[float, float]:
        return float(self.s_m[0]), float(self.s_m[-1])

    @property
    def step_m(self) -> float:
        return float(self.s_m[1] - self.s_m[0])

    @property
    def wavelength_band_m(self) -> tuple[float, float]:
        """Wavelengths the sampling can represent: from two samples up to the whole span."""

        return 2.0 * self.step_m, self.span_m[1] - self.span_m[0]

    def rms_mm(self, channel: str) -> float:
        if channel not in CHANNELS:
            raise IrregularityError(f"unknown channel {channel!r}; expected one of {CHANNELS}")
        values = getattr(self, f"{channel}_m" if channel != "roll" else "roll_rad")
        return float(np.sqrt(np.mean(np.square(np.asarray(values, dtype=float)))) * 1000.0)

    def describe(self) -> dict[str, object]:
        lo, hi = self.span_m
        slow, fast = self.wavelength_band_m
        return {
            "source": self.source,
            "samples": len(self),
            "span_m": [round(lo, 3), round(hi, 3)],
            "step_m": round(self.step_m, 6),
            "wavelength_band_m": [round(slow, 3), round(hi - lo, 3)],
            "note": "sampling cannot carry wavelengths shorter than two steps",
            "rms_mm": {name: round(self.rms_mm(name), 4) for name in CHANNELS},
        }

    def at(self, mileage_m: float) -> tuple[float, float, float, float]:
        """Linear interpolation at one mileage; ``(lateral, vertical, roll, gauge)`` in SI."""

        lo, hi = self.span_m
        if mileage_m < lo or mileage_m > hi:
            raise IrregularityError(
                f"mileage {mileage_m:.3f} m is outside the irregularity track's span "
                f"{lo:.3f}–{hi:.3f} m"
            )
        values = (
            float(np.interp(mileage_m, self.s_m, self.lateral_m)),
            float(np.interp(mileage_m, self.s_m, self.vertical_m)),
            float(np.interp(mileage_m, self.s_m, self.roll_rad)),
            float(np.interp(mileage_m, self.s_m, self.gauge_m)),
        )
        return values


def _header_factors(lines: list[str], path: Path) -> tuple[int, float, tuple[float, float, float, float]]:
    """Read ``data.type``, the mileage unit and the four unit factors."""

    header: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("!"):
            continue
        if stripped == HEADER_END:
            break
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        header[key.strip()] = value.split("!", 1)[0].strip()

    if "data.type" not in header:
        raise IrregularityError(f"{path.name}: header has no 'data.type'")
    try:
        data_type = int(float(header["data.type"]))
    except ValueError as error:
        raise IrregularityError(f"{path.name}: 'data.type' is not a number") from error
    if data_type != SUPPORTED_TYPE:
        raise IrregularityError(
            f"{path.name}: data.type = {data_type} is not supported; this reader handles "
            f"data.type = {SUPPORTED_TYPE} (lateral, vertical, roll, gauge)"
        )

    s_unit = float(header.get("data.par(1)", "1.0"))
    factors = tuple(float(header.get(key, "1.0")) for key in UNIT_KEYS)
    if s_unit <= 0.0 or any(factor <= 0.0 for factor in factors):
        raise IrregularityError(f"{path.name}: unit factors must be positive")
    return data_type, s_unit, factors  # type: ignore[return-value]


def read_tre(path: str | Path) -> IrregularityTrack:
    """Read an ASCII ``.tre`` input-function file into SI arrays."""

    source = Path(path)
    if not source.is_file():
        raise IrregularityError(f"irregularity file not found: {source}")
    raw = source.read_bytes()
    if not raw:
        raise IrregularityError(f"{source.name}: file is empty")
    if HEADER_BEGIN.encode() not in raw[:4096]:
        head = raw[:16].hex(" ")
        raise IrregularityError(
            f"{source.name}: no ASCII header.begin near the start (first bytes: {head}). "
            "This looks like Simpack's binary .tre; save it as ASCII in Simpack, or generate one "
            "with the text generator. Guessing the binary layout would silently change the "
            "excitation amplitude, so this reader refuses."
        )
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    _, s_unit, factors = _header_factors(lines, source)

    try:
        end_index = next(i for i, line in enumerate(lines) if line.strip() == HEADER_END)
    except StopIteration as error:
        raise IrregularityError(f"{source.name}: header.end not found") from error

    # ``data.par(6)`` is "read every Nth data line"; honour it instead of assuming 1.
    decimation = 1
    for line in lines[:end_index]:
        stripped = line.strip()
        if stripped.startswith("data.par(6)"):
            decimation = int(float(stripped.partition("=")[2].split("!", 1)[0]))
            break
    decimation = max(1, decimation)

    rows: list[tuple[float, float, float, float, float]] = []
    for line in lines[end_index + 1 :]:
        stripped = line.strip()
        if not stripped or stripped.startswith("!"):
            continue
        parts = stripped.split()
        if len(parts) < 5:
            raise IrregularityError(
                f"{source.name}: data line has {len(parts)} columns, expected s + four channels"
            )
        try:
            values = [float(part) for part in parts[:5]]
        except ValueError as error:
            raise IrregularityError(f"{source.name}: data line is not numeric: {stripped!r}") from error
        rows.append(tuple(values))  # type: ignore[arg-type]

    if len(rows) < 2:
        raise IrregularityError(f"{source.name}: found {len(rows)} data rows, need at least two")
    if decimation > 1:
        rows = rows[::decimation]

    array = np.asarray(rows, dtype=float)
    lateral, vertical, roll, gauge = factors
    return IrregularityTrack(
        s_m=array[:, 0] * s_unit,
        lateral_m=array[:, 1] * lateral,
        vertical_m=array[:, 2] * vertical,
        roll_rad=array[:, 3] * roll,
        gauge_m=array[:, 4] * gauge,
        source=str(source),
    )


def write_tre(path: str | Path, track: IrregularityTrack, *, comment: str = "") -> Path:
    """Write a ``.tre`` file in the same ASCII shape Simpack reads."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        HEADER_BEGIN,
        "  data.type   = 1      ! track related: lateral, vertical, roll, gauge",
        "  data.par(1) = 1.0    ! s unit: meter",
        "  data.par(2) = 1.0    ! Delta-y unit: meter",
        "  data.par(3) = 1.0    ! Delta-z unit: meter",
        "  data.par(4) = 1.0    ! Delta-phi unit: radian",
        "  data.par(5) = 1.0    ! Delta-g unit: meter",
        "  data.par(6) = 1      ! read every data line",
        HEADER_END,
        "",
    ]
    if comment:
        lines.append(f"! {comment}")
    lines.append("! s[m] Delta-y[m] Delta-z[m] Delta-phi[rad] Delta-g[m]")
    for index in range(len(track)):
        lines.append(
            f"{track.s_m[index]:.7f}  {track.lateral_m[index]:.10e}  "
            f"{track.vertical_m[index]:.10e}  {track.roll_rad[index]:.10e}  "
            f"{track.gauge_m[index]:.10e}"
        )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return target


def window_factor(
    mileage_m: np.ndarray,
    *,
    start_m: float,
    end_m: float,
    fade_m: float = 0.0,
) -> np.ndarray:
    """Simpack's ``track.excit.start/end/fade`` as a multiplication factor.

    Inside ``[start, end]`` the factor is 1; through the fade length it passes smoothly to 0.
    The transition is a half-cosine, which is the only shape that is both C1 and needs a single
    parameter; ``docs/SIMPACK_IRREGULARITY_MINING_2026-10-23.md`` records that Simpack's own
    shape is not documented, so this choice is written down rather than assumed to match.
    """

    if end_m < start_m:
        raise IrregularityError(f"excitation window is empty: start {start_m} > end {end_m}")
    if fade_m < 0.0:
        raise IrregularityError("fade length must not be negative")
    mileage = np.asarray(mileage_m, dtype=float)
    factor = np.zeros_like(mileage)
    inside = (mileage >= start_m) & (mileage <= end_m)
    factor[inside] = 1.0
    if fade_m > 0.0:
        rise = inside & (mileage < start_m + fade_m)
        factor[rise] = 0.5 - 0.5 * np.cos(np.pi * (mileage[rise] - start_m) / fade_m)
        fall = inside & (mileage > end_m - fade_m)
        factor[fall] = 0.5 - 0.5 * np.cos(np.pi * (end_m - mileage[fall]) / fade_m)
    return factor


def rail_offsets(
    lateral_m: float,
    vertical_m: float,
    roll_rad: float,
    gauge_m: float,
    *,
    half_gauge_m: float,
    side: str,
) -> tuple[float, float]:
    """Turn the four track channels into one rail's ``(dy, dz)`` in metres.

    ``roll`` lifts one rail and drops the other (that is what "cross level" means), and ``gauge``
    widens or narrows the pair, so both act as a half amplitude on each side.  The sign
    convention matches our case files: ``side="left"`` is the negative-``y`` rail.
    """

    if side not in {"left", "right"}:
        raise IrregularityError(f"side must be 'left' or 'right', not {side!r}")
    sign = -1.0 if side == "left" else 1.0
    dy = lateral_m + sign * 0.5 * gauge_m
    dz = vertical_m + sign * roll_rad * half_gauge_m
    return dy, dz


def dense_stations(
    track: IrregularityTrack,
    *,
    start_m: float,
    end_m: float,
    fade_m: float = 0.0,
    interval_m: float | None = None,
) -> list[tuple[float, float, float, float, float]]:
    """Sample the excitation on a mileage grid, ready to become stations of a derived case.

    Returns ``(s, lateral, vertical, roll, gauge)`` with the window already applied, so a case
    built from these stations needs no further windowing.
    """

    lo = max(start_m, track.span_m[0])
    hi = min(end_m, track.span_m[1])
    if hi - lo < 1.0e-9:
        raise IrregularityError(
            f"excitation window {start_m}–{end_m} m does not overlap the track span "
            f"{track.span_m[0]:.3f}–{track.span_m[1]:.3f} m"
        )
    step = float(interval_m) if interval_m else track.step_m
    if step <= 0.0:
        raise IrregularityError("interval must be positive")
    count = int(math.floor((hi - lo) / step)) + 1
    grid = lo + np.arange(count, dtype=float) * step
    factor = window_factor(grid, start_m=start_m, end_m=end_m, fade_m=fade_m)
    lateral = np.interp(grid, track.s_m, track.lateral_m) * factor
    vertical = np.interp(grid, track.s_m, track.vertical_m) * factor
    roll = np.interp(grid, track.s_m, track.roll_rad) * factor
    gauge = np.interp(grid, track.s_m, track.gauge_m) * factor
    return [
        (float(grid[i]), float(lateral[i]), float(vertical[i]), float(roll[i]), float(gauge[i]))
        for i in range(count)
    ]


def scaled_track(
    track: IrregularityTrack,
    *,
    scale: float = 1.0,
    channels: tuple[str, ...] = CHANNELS,
    start_m: float | None = None,
    end_m: float | None = None,
    fade_m: float = 0.0,
) -> IrregularityTrack:
    """Return the track with the window, the channel selection and the amplitude applied.

    The windowing happens here, once, on the track grid: the sampler that runs inside every
    dynamics evaluation then only reads numbers and carries no branches.
    """

    if scale < 0.0 or not math.isfinite(scale):
        raise IrregularityError("scale must be a finite, non-negative number")
    unknown = [name for name in channels if name not in CHANNELS]
    if unknown:
        raise IrregularityError(f"unknown channel(s) {unknown}; expected a subset of {CHANNELS}")
    lo, hi = track.span_m
    window_start = lo if start_m is None else float(start_m)
    window_end = hi if end_m is None else float(end_m)
    factor = window_factor(track.s_m, start_m=window_start, end_m=window_end, fade_m=fade_m) * scale
    values = {}
    for name in CHANNELS:
        field = "roll_rad" if name == "roll" else f"{name}_m"
        source = np.asarray(getattr(track, field), dtype=float)
        values[name] = source * factor if name in channels else np.zeros_like(track.s_m)
    return IrregularityTrack(
        s_m=track.s_m,
        lateral_m=values["lateral"],
        vertical_m=values["vertical"],
        roll_rad=values["roll"],
        gauge_m=values["gauge"],
        source=track.source,
    )


@dataclass(frozen=True)
class ShiftedSeries:
    """A rail profile series with its own side's irregularity added, sample by sample.

    ``velch.contact`` asks a series for the running surface at a mileage; the answer carries the
    surface (``profile``) and its longitudinal slope (``dz_ds``).  An irregularity is exactly a
    mileage-dependent offset of that surface, so the honest place to apply it is here: the contact
    search keeps working on one profile per evaluation and never learns about ``.tre`` files.
    """

    inner: object
    track: IrregularityTrack
    side: str
    half_gauge_m: float
    derivative_step_m: float = 1.0e-3

    def covers(self, s_m: float) -> bool:
        return bool(self.inner.covers(s_m))

    @property
    def lowest_m(self) -> float:
        return float(self.inner.lowest_m)

    @property
    def highest_m(self) -> float:
        return float(self.inner.highest_m)

    def mileages(self):
        return tuple(self.inner.mileages())

    def _offsets(self, s_m: float) -> tuple[float, float]:
        lo, hi = self.track.span_m
        clamped = min(max(float(s_m), lo), hi)
        lateral, vertical, roll, gauge = self.track.at(clamped)
        return rail_offsets(lateral, vertical, roll, gauge,
                            half_gauge_m=self.half_gauge_m, side=self.side)

    def sample(self, s_m: float, direction: int = 1):
        from dataclasses import replace

        base = self.inner.sample(s_m, direction)
        dy, dz = self._offsets(s_m)
        lo, hi = self.track.span_m
        step = self.derivative_step_m
        left = min(max(float(s_m) - step, lo), hi)
        right = min(max(float(s_m) + step, lo), hi)
        slope = 0.0
        if right > left:
            slope = (self._offsets(right)[1] - self._offsets(left)[1]) / (right - left)
        profile = replace(
            base.profile,
            y_m=np.asarray(base.profile.y_m, dtype=float) + dy,
            z_m=np.asarray(base.profile.z_m, dtype=float) + dz,
            source=f"{base.profile.source}+irregularity",
        )
        return replace(base, profile=profile, dz_ds=base.dz_ds + slope)


@dataclass(frozen=True)
class CurveSeries:
    """A rail series shifted onto a circular alignment ``y(s) = s^2/(2R)``.

    The rigid track kernel samples profiles by mileage and has no placement hook of its own, so a
    geometric curve on a 35-coordinate case moved the *vehicle* onto the arc while the rails stayed
    straight.  Measured: the wheels ended 45.5 mm beside their rails and the contact rows carried
    **1.95 MN**, which no seat can resolve.  Publishing the alignment here puts it where every
    consumer already looks -- the sampled profile -- so rigid, floating and modal tracks all see
    the same curved rail.

    ``cant_m`` raises the outer rail by half the gauge times ``sin(phi)``; the surface rotation is
    ``RolledSeries``' job, applied outside this wrapper.
    """

    inner: object
    radius_m: float
    origin_m: float
    side: int = 1
    cant_m: float = 0.0
    half_gauge_m: float = 0.7465

    def covers(self, s_m: float) -> bool:
        return bool(self.inner.covers(s_m))

    def sample(self, s_m: float, direction: int = 1):
        base = self.inner.sample(s_m, direction)
        offset = float(s_m) - float(self.origin_m)
        lateral = offset * offset / (2.0 * float(self.radius_m))
        angle = 0.0
        if self.cant_m:
            angle = math.asin(max(-1.0, min(1.0, float(self.cant_m) / (2.0 * self.half_gauge_m))))
        rise = 0.5 * 2.0 * self.half_gauge_m * math.sin(angle) if angle else 0.0
        shift = rise if self.side > 0 else -rise
        profile = replace(
            base.profile,
            y_m=base.profile.y_m + lateral,
            z_m=base.profile.z_m + shift,
            source=f"{base.profile.source}+curve",
        )
        # ``dz_ds`` is the *vertical* slope of the sampled surface; a lateral shift of the same
        # surface does not tilt it.  Adding the plan slope here rotated the rail by up to 1 degree
        # and left a residual the seat could not remove (measured: every speed from 10 to 100 km/h
        # failed with `gtol termination condition is satisfied`).
        return replace(base, profile=profile)


@dataclass(frozen=True)
class RolledSeries:
    """A rail profile series whose cross-section is turned with the track plane.

    Cant is not a vertical offset: the whole track plane rotates by ``phi = cant / gauge``, so each
    rail surface rotates about its own longitudinal axis as well as moving up or down.  Publishing
    the level difference alone (``dz = +-rise``, no rotation) puts the wheel on its flange root and
    leaves the static seat with no solution — measured at R = 1100 m with 107 mm of cant, where the
    seat failed after every seed.  Rotating here means the contact search sees the surface the
    vehicle really rides on, and its normal, without learning anything about cant.

    The rotation is about the rail's own centreline, which is the origin of ``profile.y_m/z_m``.
    """

    inner: object
    angle_rad: float

    def covers(self, s_m: float) -> bool:
        return bool(self.inner.covers(s_m))

    @property
    def lowest_m(self) -> float:
        return float(self.inner.lowest_m)

    @property
    def highest_m(self) -> float:
        return float(self.inner.highest_m)

    def mileages(self):
        return tuple(self.inner.mileages())

    def sample(self, s_m: float, direction: int = 1):
        from dataclasses import replace

        import numpy as np

        base = self.inner.sample(s_m, direction)
        if self.angle_rad == 0.0:
            return base
        cosine = float(np.cos(self.angle_rad))
        sine = float(np.sin(self.angle_rad))
        y = np.asarray(base.profile.y_m, dtype=float)
        z = np.asarray(base.profile.z_m, dtype=float)
        profile = replace(
            base.profile,
            y_m=y * cosine - z * sine,
            z_m=y * sine + z * cosine,
            source=f"{base.profile.source}+roll",
        )
        # The longitudinal slope is unchanged by a rotation about the longitudinal axis: the
        # tangent stays a tangent, and dz/ds of the surface is the same curve turned.
        return replace(base, profile=profile)


def roll_rails(rails, angle_rad: float):
    """Wrap every rail body's series with :class:`RolledSeries` for one track-plane angle."""

    from dataclasses import replace

    if angle_rad == 0.0:
        return tuple(rails)
    rolled = []
    for rail in rails:
        bodies = tuple(
            replace(body, series=RolledSeries(body.series, angle_rad))
            for body in rail.bodies
        )
        rolled.append(replace(rail, bodies=bodies))
    return tuple(rolled)


def shift_rails(rails, track: IrregularityTrack, *, half_gauge_m: float):
    """Wrap every rail body's series with :class:`ShiftedSeries` for its own side."""

    from dataclasses import replace

    shifted = []
    for rail in rails:
        side = "left" if str(rail.id).endswith("left") else "right"
        bodies = tuple(
            replace(body, series=ShiftedSeries(body.series, track, side, half_gauge_m))
            for body in rail.bodies
        )
        shifted.append(replace(rail, bodies=bodies))
    return tuple(shifted)


def describe_application(track, *, start_m, end_m, fade_m, scale, channels) -> dict:
    """The record that belongs in the case sidecar: what was applied, and from which file."""

    slow, fast = track.wavelength_band_m
    return {
        "source": track.source,
        "samples": len(track),
        "step_m": round(track.step_m, 6),
        "channels": list(channels),
        "start_m": start_m,
        "end_m": end_m,
        "fade_m": fade_m,
        "scale": scale,
        "wavelength_band_m": [round(slow, 4), round(fast, 4)],
        "fade_shape": "half-cosine (Simpack's own shape is undocumented; see SIMPACK_IRREGULARITY_MINING)",
        "applied_at": "sampled rail surface (Simpack applies at the track centreline reference)",
    }
