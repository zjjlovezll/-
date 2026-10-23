"""S3: the generator must reproduce the spectrum it claims, and refuse impossible requests."""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.irregularity_gen import (
    MIN_WAVELENGTH_M,
    SPECTRA,
    IrregularityGenerationError,
    band_rms,
    generate,
    octave_bands,
    spectrum,
)


def test_the_shortest_wavelength_sets_the_step() -> None:
    track = generate(length_m=20.0, step_m=0.025, shortest_m=0.05, longest_m=10.0, seed=1)
    assert track.step_m == pytest.approx(0.025)
    assert track.s_m.size == pytest.approx(20.0 / 0.025 + 1)


def test_a_step_coarser_than_nyquist_is_refused_with_the_way_out() -> None:
    with pytest.raises(IrregularityGenerationError, match="Nyquist"):
        generate(length_m=20.0, step_m=0.05, shortest_m=0.05)
    with pytest.raises(IrregularityGenerationError, match="0.025"):
        generate(length_m=20.0, step_m=0.05, shortest_m=0.05)


@pytest.mark.parametrize("name", sorted(SPECTRA))
def test_every_spectrum_lands_within_ten_percent_band_by_band(name: str) -> None:
    track = generate(spectrum_name=name, length_m=200.0, step_m=0.025,
                     shortest_m=0.05, longest_m=25.0, seed=7)
    rows = [row for row in band_rms(track) if row["analytic_rms_mm"] > 1e-4]
    assert rows, "no band carried measurable power"
    for row in rows:
        assert 0.9 <= row["ratio"] <= 1.1, (
            f"{name}: {row['short_m']:.3f}-{row['long_m']:.3f} m measured "
            f"{row['measured_rms_mm']:.4f} vs analytic {row['analytic_rms_mm']:.4f} mm"
        )


def test_the_measured_rms_matches_the_analytic_band_power() -> None:
    track = generate(length_m=400.0, step_m=0.025, shortest_m=0.05, longest_m=25.0, seed=11)
    spec = spectrum("german_low")
    omega_lo = 2.0 * math.pi / 25.0
    omega_hi = 2.0 * math.pi / 0.05
    analytic = math.sqrt(spec.band_power(omega_lo, omega_hi)) * 1000.0
    assert track.rms_mm("vertical") == pytest.approx(analytic, rel=0.05)


def test_generation_is_deterministic_per_seed_and_differs_across_seeds() -> None:
    first = generate(length_m=50.0, step_m=0.025, seed=3)
    same = generate(length_m=50.0, step_m=0.025, seed=3)
    other = generate(length_m=50.0, step_m=0.025, seed=4)
    assert np.array_equal(first.vertical_m, same.vertical_m)
    assert not np.array_equal(first.vertical_m, other.vertical_m)


def test_channels_not_asked_for_are_exactly_zero() -> None:
    track = generate(length_m=50.0, step_m=0.025, channels=("vertical",))
    attributes = {"lateral": "lateral_m", "roll": "roll_rad", "gauge": "gauge_m"}
    for channel, attribute in attributes.items():
        assert np.all(getattr(track, attribute) == 0.0), channel


def test_unknown_spectrum_names_list_what_exists() -> None:
    with pytest.raises(IrregularityGenerationError, match="german_low"):
        generate(spectrum_name="not_a_spectrum", step_m=0.025)


def test_octave_bands_stay_inside_the_window() -> None:
    bands = octave_bands(MIN_WAVELENGTH_M, 25.0)
    assert bands[0][1] == pytest.approx(25.0)
    assert bands[-1][0] == pytest.approx(MIN_WAVELENGTH_M)
    for short, long in bands:
        assert short < long
        assert 0.05 <= short and long <= 25.0
