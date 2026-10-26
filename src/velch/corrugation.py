"""Put a periodic rail corrugation into the model, in whichever form the run needs.

A corrugation is periodic wear on the rail top: a lift ``sum_n A_n cos(2 pi n (s - s0) / L)``
along the mileage ``s``.  The solver never sees "the rail"; it sees one of three
representations, and choosing the wrong one is how a corrugation silently does
nothing or silently loses amplitude:

1. **the station table** — the case lists mileage -> profile file (a ``.prr``), and
   :class:`velch.profiles.ProfileSeries` interpolates **linearly** between stations.
   This is the only representation that is a property of the rail itself, so it is
   the one that survives into every downstream tool, but it is also the one that
   filters the defect: linear interpolation of a sinusoid sampled every ``h``
   passes the fundamental with amplitude factor ``|sinc(pi h / lambda)|^2``.
   :func:`required_step_m` inverts that relation, and the honest answer for
   25 mm wavelength at 3 % loss is ``h <= 5 mm`` — thousands of files over a
   useful patch.
2. **a ``.tre`` track-excitation file** — applied at the *sampling* layer by
   :class:`velch.irregularity.ShiftedSeries`, independent of the station spacing,
   so 2.5 mm sampling of the defect costs one file.  Measured against the dense
   station table it agrees to **0.13 %** once an axle actually crosses the patch
   (``docs/PRR_CORRUGATION...``), so it is the right tool for a study of the
   inversion.  It is *not* the rail geometry: a case has to carry the ``.tre``.
3. **an analytic lift** — :meth:`Corrugation.at`, for post-processing and for
   building either of the above.

Two traps this module exists to prevent, both found by reproducing them:

* a station table that does not start at ``0 m`` seats the vehicle on the
  hung-branch solution even when the surface is identical everywhere (the
  near-singular eight-patch seat behind O010), and
* a table whose stations are too sparse does not fail — it just returns a
  shallower defect, which reads as a physics result.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .irregularity import IrregularityTrack


class CorrugationError(ValueError):
    """Raised when a corrugation cannot be built into the requested form."""


@dataclass(frozen=True)
class Corrugation:
    """A periodic depth profile on the rail top, in metres along the track."""

    period_m: float
    depth_m: float
    harmonics: tuple[float, ...] = (1.0,)
    phase_origin_m: float = 0.0

    def __post_init__(self) -> None:
        if self.period_m <= 0.0:
            raise CorrugationError(f"period_m must be positive, got {self.period_m!r}")
        if self.depth_m <= 0.0:
            raise CorrugationError(f"depth_m must be positive, got {self.depth_m!r}")
        harmonics = tuple(float(value) for value in self.harmonics)
        if not harmonics:
            raise CorrugationError("harmonics must name at least the fundamental")
        if any(value < 0.0 for value in harmonics):
            raise CorrugationError(f"harmonic amplitudes must not be negative: {harmonics!r}")
        if not any(value > 0.0 for value in harmonics):
            raise CorrugationError("every harmonic amplitude is zero, so there is no defect")
        object.__setattr__(self, "harmonics", harmonics)

    @property
    def order(self) -> int:
        return len(self.harmonics)

    def wavelength_m(self, order: int = 1) -> float:
        return self.period_m / max(1, int(order))

    def frequency_hz(self, speed_m_s: float, order: int = 1) -> float:
        """Passing frequency of harmonic ``order`` at this speed."""
        return max(1, int(order)) * speed_m_s / self.period_m

    def peak_to_peak(self) -> float:
        """Peak-to-peak depth; every cosine peaks at the same mileage only if in phase."""
        return 2.0 * self.depth_m * sum(self.harmonics)

    def at(self, s_m: float) -> float:
        """Lift of the rail top at mileage ``s_m`` (zero-order term excluded)."""
        offset = s_m - self.phase_origin_m
        total = 0.0
        for index, amplitude in enumerate(self.harmonics, start=1):
            total += amplitude * math.cos(2.0 * math.pi * index * offset / self.period_m)
        return self.depth_m * total

    def samples(self, start_m: float, end_m: float, step_m: float) -> tuple[np.ndarray, np.ndarray]:
        """Mileage grid and lift on it, inclusive of ``start_m``."""
        if step_m <= 0.0:
            raise CorrugationError(f"step_m must be positive, got {step_m!r}")
        if end_m <= start_m:
            raise CorrugationError(f"end_m must exceed start_m, got {start_m!r} / {end_m!r}")
        count = int(math.floor((end_m - start_m) / step_m + 1.0e-9)) + 1
        mileage = start_m + np.arange(count, dtype=float) * step_m
        lift = np.array([self.at(float(value)) for value in mileage], dtype=float)
        return mileage, lift

    def track(self, *, start_m: float, periods: int, step_m: float) -> IrregularityTrack:
        """The same defect as a vertical-only ``.tre`` track record."""
        if periods <= 0:
            raise CorrugationError(f"periods must be positive, got {periods!r}")
        end_m = start_m + periods * self.period_m
        mileage, lift = self.samples(start_m, end_m, step_m)
        zeros = np.zeros_like(mileage)
        return IrregularityTrack(
            s_m=mileage,
            lateral_m=zeros,
            vertical_m=lift,
            roll_rad=zeros,
            gauge_m=zeros,
            source=(
                f"corrugation {self.period_m:g} m, depth {self.depth_m * 1e6:g} um, "
                f"{self.order} harmonic(s), stations every {step_m:g} m"
            ),
        )


def interpolation_gain(step_m: float, wavelength_m: float) -> float:
    """Amplitude factor of the linearly interpolated fundamental.

    Sampling a sinusoid of wavelength ``l`` every ``h`` and joining the samples
    with straight lines multiplies the fundamental by ``|sinc(pi h / l)|^2``
    (the sampling holds the values, the interpolation is a first-order hold).
    """
    if wavelength_m <= 0.0:
        raise CorrugationError(f"wavelength_m must be positive, got {wavelength_m!r}")
    if step_m <= 0.0:
        raise CorrugationError(f"step_m must be positive, got {step_m!r}")
    ratio = math.pi * step_m / wavelength_m
    return (math.sin(ratio) / ratio) ** 2


def required_step_m(wavelength_m: float, *, tolerance: float = 0.03) -> float:
    """Largest station spacing whose interpolation loss stays within ``tolerance``.

    ``tolerance`` is a fraction of lost amplitude: ``0.03`` means "at most 3 %
    shallower than the real defect".  Solved by bisection on
    :func:`interpolation_gain` because it is monotone in the spacing.
    """
    if not 0.0 < tolerance < 1.0:
        raise CorrugationError(f"tolerance must be a fraction in (0, 1), got {tolerance!r}")
    target = 1.0 - float(tolerance)
    low, high = 1.0e-6 * wavelength_m, 0.5 * wavelength_m
    if interpolation_gain(low, wavelength_m) < target:
        raise CorrugationError(
            f"no spacing reaches a gain of {target:.4f} at wavelength {wavelength_m:g} m"
        )
    for _ in range(80):
        middle = 0.5 * (low + high)
        if interpolation_gain(middle, wavelength_m) >= target:
            low = middle
        else:
            high = middle
    return low


def alias_free_step_m(wavelength_m: float, *, order: int = 1) -> float:
    """Spacing above which harmonic ``order`` would alias past Nyquist."""
    return wavelength_m / (2.0 * max(1, int(order)))


def lifted_profile_text(text: str, lift_m: float, *, z_sign: float = -1.0) -> str:
    """Return the PRR text with the rail top raised by ``lift_m``.

    The file stores ``z``; the physical height is ``z_sign * z`` (this corpus's
    profiles carry ``z_sign = -1``).  Raising the surface therefore changes the
    stored value by ``lift / z_sign``, which keeps one implementation valid for
    both conventions.  Only the two numeric columns of the point block are
    rewritten, so units, comments and the spline header survive byte for byte.
    """
    if z_sign == 0.0:
        raise CorrugationError("z_sign must not be zero")
    delta = float(lift_m) / float(z_sign)
    lines = text.splitlines(keepends=True)
    try:
        start = next(index for index, line in enumerate(lines) if "point.begin" in line)
        end = next(index for index, line in enumerate(lines) if "point.end" in line)
    except StopIteration as exc:
        raise CorrugationError("PRR point block is missing") from exc
    for index in range(start + 1, end):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("!"):
            continue
        fields = stripped.split()
        if len(fields) < 2:
            continue
        try:
            y_value = float(fields[0])
            z_value = float(fields[1])
        except ValueError:
            continue
        lines[index] = f" {y_value:12.8f} {z_value + delta:12.8f}\n"
    return "".join(lines)


def station_mileages(
    *,
    start_m: float,
    end_m: float,
    step_m: float,
    run_end_m: float,
) -> list[float]:
    """Mileages for a dense-station corrugation, padded so the run can seat.

    The table always begins at ``0.0`` and always reaches past ``run_end_m``:
    a table that starts later seats the vehicle on the hung branch even when the
    surface is identical everywhere (reproduced: first station 33 m -> FAILED,
    0 m -> OK), and a table that ends under the front axle lets that rail go
    inactive and the vehicle fall.
    """
    if step_m <= 0.0:
        raise CorrugationError(f"step_m must be positive, got {step_m!r}")
    if end_m <= start_m:
        raise CorrugationError(f"end_m must exceed start_m, got {start_m!r} / {end_m!r}")
    if run_end_m <= end_m:
        raise CorrugationError(
            f"run_end_m ({run_end_m:g} m) must reach past the patch end ({end_m:g} m)"
        )
    count = int(math.floor((end_m - start_m) / step_m + 1.0e-9)) + 1
    inside = [start_m + index * step_m for index in range(count)]
    outside = [0.0, start_m, end_m, run_end_m]
    return sorted({round(value, 9) for value in (*inside, *outside)})


def write_station_table(
    base_text: str,
    corrugation: Corrugation,
    *,
    directory: Path,
    start_m: float,
    end_m: float,
    step_m: float,
    run_end_m: float,
    z_sign: float = -1.0,
    prefix: str = "profile",
) -> list[tuple[float, Path]]:
    """Write one PRR per station and return ``(mileage, path)`` in order."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stations: list[tuple[float, Path]] = []
    for index, mileage in enumerate(
        station_mileages(start_m=start_m, end_m=end_m, step_m=step_m, run_end_m=run_end_m)
    ):
        inside = start_m <= mileage <= end_m
        lift = corrugation.at(mileage) if inside else 0.0
        path = directory / f"{prefix}_{index:05d}.prr"
        path.write_text(lifted_profile_text(base_text, lift, z_sign=z_sign), encoding="utf-8")
        stations.append((mileage, path))
    return stations
