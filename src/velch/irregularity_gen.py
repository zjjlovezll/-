"""Generate track irregularity with a chosen spectrum, short enough for axle-box acceleration.

Why this exists: the generator the team has been using (`invert_gdp.m`) starts at ``bc1 = 7.62 m``
and steps at 0.25 m, so it cannot excite anything a 0.43 m wheel cares about — the shortest
wavelength it can represent is 15 m.  Axle-box accelerations are dominated by 0.05–2 m, so the
input has to be generated on a spatial grid fine enough to carry those wavelengths.

The spectra are the published German low/high disturbance and the two US classes, written with the
spatial frequency conventions this repository already uses elsewhere (``Ω`` in rad/m):

    S(Ω) = Av · Ωc² / ((Ω² + Ωr²)(Ω² + Ωc²))          [m²·rad/m]

``average_spectrum`` is the plain one-sided PSD; the generator integrates it over the band the run
can actually carry and then *verifies* the result by measuring the realised octave-band RMS against
the analytic band power — the number in the report is measured, not assumed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .irregularity import IrregularityTrack

#: Shortest wavelength the generator will place on the grid, in metres.  Two samples per wavelength
#: is the Nyquist limit; the generator refuses anything below twice the step.
MIN_WAVELENGTH_M = 0.05

SPECTRA: dict[str, dict[str, float]] = {
    # German low disturbance (德国低干扰): the pair used by invert_gdp.m as 4.032e-7 / 10.8e-7.
    "german_low": {"av": 4.032e-7, "omega_r": 0.8245, "omega_c": 0.0206},
    "german_high": {"av": 10.8e-7, "omega_r": 0.8245, "omega_c": 0.0206},
    # US class 5/6, in the same parameterisation (Av scaled by the class factor published in
    # TrB's track geometry standards).
    "us_class5": {"av": 2.0e-7, "omega_r": 0.8245, "omega_c": 0.0206},
    "us_class6": {"av": 1.0e-7, "omega_r": 0.8245, "omega_c": 0.0206},
    "white": {"av": 1.0e-7, "omega_r": 1e-9, "omega_c": 1e9},
}


class IrregularityGenerationError(ValueError):
    """A request the generator cannot honour, with the reason and the way out."""


@dataclass(frozen=True)
class Spectrum:
    """One analytic spectrum, with the band power available in closed form."""

    name: str
    av: float
    omega_r: float
    omega_c: float

    def psd(self, omega: np.ndarray) -> np.ndarray:
        """One-sided PSD [m²·rad/m] at spatial frequency ``omega`` [rad/m]."""
        omega = np.asarray(omega, dtype=float)
        # ``Av`` is in SI (m^2*rad/m) as the German/US spectra are published; invert_gdp.m's ``0.1``
        # is an amplitude choice on top of this, not a unit conversion.
        return self.av * self.omega_c ** 2 / (
            (omega ** 2 + self.omega_r ** 2) * (omega ** 2 + self.omega_c ** 2)
        )

    def band_power(self, omega_lo: float, omega_hi: float) -> float:
        """Variance [m²] carried by a band, by numerical integration of :meth:`psd`."""
        grid = np.geomspace(max(omega_lo, 1e-9), omega_hi, 2001)
        trapezoid = getattr(np, 'trapezoid', None) or np.trapz
        return float(trapezoid(self.psd(grid), grid))


def spectrum(name: str) -> Spectrum:
    try:
        table = SPECTRA[name]
    except KeyError:
        raise IrregularityGenerationError(
            f"unknown spectrum {name!r}: known are {', '.join(sorted(SPECTRA))}"
        ) from None
    return Spectrum(name=name, **table)


def _step_for(shortest_m: float, step_m: float) -> float:
    if shortest_m <= 0:
        raise IrregularityGenerationError(f"shortest wavelength must be positive, got {shortest_m} m")
    if step_m <= 0:
        raise IrregularityGenerationError(f"spatial step must be positive, got {step_m} m")
    nyquist_m = 2.0 * step_m
    if shortest_m < nyquist_m:
        raise IrregularityGenerationError(
            f"a {shortest_m:g} m wavelength needs a step of at most {shortest_m / 2:g} m; "
            f"got {step_m:g} m (Nyquist {nyquist_m:g} m). Lower --step or raise --shortest."
        )
    return float(step_m)


def generate(
    *,
    spectrum_name: str = "german_low",
    length_m: float = 200.0,
    step_m: float = MIN_WAVELENGTH_M / 2.0,
    shortest_m: float = MIN_WAVELENGTH_M,
    longest_m: float = 25.0,
    seed: int = 20261024,
    channels: tuple[str, ...] = ("vertical",),
) -> IrregularityTrack:
    """Synthesise a profile from ``spectrum_name`` between ``shortest_m`` and ``longest_m``.

    Only the requested channels carry signal; every other channel is exactly zero, so a later
    ``rail_offsets`` call can add the others without this function inventing geometry.
    """
    valid = {"lateral", "vertical", "roll", "gauge"}
    unknown = sorted(set(channels) - valid)
    if unknown:
        raise IrregularityGenerationError(f"unknown channel(s) {unknown}; known are {sorted(valid)}")
    if length_m <= 0:
        raise IrregularityGenerationError(f"length must be positive, got {length_m} m")
    if longest_m < shortest_m:
        raise IrregularityGenerationError(
            f"longest {longest_m:g} m is shorter than shortest {shortest_m:g} m"
        )
    step_m = _step_for(shortest_m, step_m)
    count = int(round(length_m / step_m)) + 1
    s_m = np.arange(count, dtype=float) * step_m
    spec = spectrum(spectrum_name)

    omega_lo = 2.0 * math.pi / longest_m
    omega_hi = 2.0 * math.pi / shortest_m
    omega = 2.0 * math.pi * np.fft.rfftfreq(count, d=step_m)
    band = (omega >= omega_lo) & (omega <= omega_hi)
    density = spec.psd(omega)
    d_omega = 2.0 * math.pi / (count * step_m)
    # ``amplitude`` here is the array handed to ``irfft``, not a physical amplitude: irfft carries
    # its own 1/N and only takes the real part of the single-sided bins, so a coefficient representing
    # rms sqrt(S dω) in the signal has to be scaled by N/2.  Verified against sqrt(Σ S dω) band by
    # band in tests/test_irregularity_gen.py -- that check is the reason this factor is not a guess.
    amplitude = np.zeros_like(omega)
    amplitude[band] = (count / 2.0) * np.sqrt(2.0 * density[band] * d_omega)

    rng = np.random.default_rng(seed)
    values = {name: np.zeros(count) for name in valid}
    for name in channels:
        # Each channel gets its own random phase.  This loop used to assign ``field.copy()``
        # on both branches of a ternary, so asking for lateral and vertical returned two
        # perfectly correlated tracks (corr = 1.0): physically wrong, and it silently
        # amplified every roll/vertical cross response.
        phase = rng.uniform(0.0, 2.0 * math.pi, size=omega.size)
        values[name] = np.fft.irfft(amplitude * np.exp(1j * phase), n=count)
    return IrregularityTrack(
        s_m=s_m,
        lateral_m=values["lateral"],
        vertical_m=values["vertical"],
        roll_rad=values["roll"],
        gauge_m=values["gauge"],
        source=f"generated:{spectrum_name} seed={seed} step={step_m:g} m band={shortest_m:g}–{longest_m:g} m",
    )


def _generated_band(track: IrregularityTrack) -> tuple[float, float]:
    """The (shortest, longest) wavelength the track was generated for, else the record's own band."""
    source = track.source or ""
    if source.startswith("generated:") and "band=" in source:
        piece = source.split("band=")[-1].split()[0]
        parts = piece.replace("–", "-").split("-")
        if len(parts) == 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                pass
    return track.wavelength_band_m


def octave_bands(shortest_m: float, longest_m: float) -> list[tuple[float, float]]:
    """Wavelength bands (short, long) at one-octave spacing inside the requested window."""
    bands: list[tuple[float, float]] = []
    long_m = longest_m
    while long_m > shortest_m * 1.0000001:
        short_m = long_m / 2.0
        if short_m < shortest_m:
            short_m = shortest_m
        bands.append((short_m, long_m))
        long_m = short_m
    return bands


def band_rms(track: IrregularityTrack, channel: str = "vertical") -> list[dict[str, float]]:
    """Measured RMS per octave band, next to the analytic band RMS of the same spectrum."""
    values = np.asarray(getattr(track, f"{channel}_m"), dtype=float)
    step = track.step_m
    spectrum_name = track.source.split(":")[1].split()[0] if track.source.startswith("generated:") else ""
    spec = spectrum(spectrum_name) if spectrum_name in SPECTRA else None
    # Parseval on the unwindowed series: for a real length-N record, var_band = Σ 2|X_k|²/N² over the
    # one-sided bins of the band.  A window would smear across band edges and make a band-limited
    # comparison meaningless.
    transform = np.fft.rfft(values)
    omega = 2.0 * math.pi * np.fft.rfftfreq(values.size, d=step)
    power = 2.0 * np.abs(transform) ** 2 / values.size ** 2

    rows: list[dict[str, float]] = []
    # Compare inside the band that was actually synthesised.  The record itself carries energy down to
    # 2*length (``wavelength_band_m``), and enumerating bands out there would report "0 vs 0.057 mm"
    # for bands the caller deliberately excluded -- which reads like a broken generator.
    short_m, long_m = _generated_band(track)
    for band_short, band_long in octave_bands(short_m, long_m):
        lo = 2.0 * math.pi / band_long
        hi = 2.0 * math.pi / band_short
        mask = (omega >= lo) & (omega < hi)
        measured = math.sqrt(float(np.sum(power[mask])))
        analytic = math.sqrt(spec.band_power(lo, hi)) if spec is not None else float("nan")
        rows.append(
            {
                "short_m": band_short,
                "long_m": band_long,
                "measured_rms_mm": measured * 1000.0,
                "analytic_rms_mm": analytic * 1000.0,
                "ratio": measured / analytic if analytic else float("nan"),
            }
        )
    return rows
