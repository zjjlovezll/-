"""Tests for the frequency-domain decomposition, against known analytic modes."""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.inverse.spectral import SpectralError, find_peaks, spectral_matrix

SAMPLE_RATE_HZ = 1000.0


def _two_dof(*, seconds: float = 60.0, seed: int = 20261028, damping: float = 0.02):
    """A 2-dof chain: analytic modal frequencies 22.0 and 57.6 Hz."""
    mass = 2.0
    stiffness = 1.0e5
    matrix = stiffness * np.array([[2.0, -1.0], [-1.0, 1.0]])
    eigenvalues, vectors = np.linalg.eigh(matrix / mass)
    omega = np.sqrt(eigenvalues)
    dt = 1.0 / SAMPLE_RATE_HZ
    count = int(seconds * SAMPLE_RATE_HZ)
    rng = np.random.default_rng(seed)
    state = np.zeros(4)
    response = np.zeros((count, 2))
    for step in range(count):
        displacement = state[:2]
        velocity = state[2:]
        acceleration = -2.0 * damping * omega * velocity - omega ** 2 * displacement
        acceleration = acceleration + rng.normal(0.0, 1.0e4, size=2) / mass
        state[2:] = velocity + acceleration * dt
        state[:2] = displacement + state[2:] * dt
        response[step] = vectors @ state[:2]
    return response, omega / (2.0 * math.pi)


def test_peaks_land_on_the_analytic_modes():
    response, expected = _two_dof()
    decomposition = spectral_matrix(response, sample_rate_hz=SAMPLE_RATE_HZ, segment_seconds=8.0,
                                   band=(5.0, 200.0))
    peaks = find_peaks(decomposition, prominence_db=3.0)
    found = np.array([peak.frequency_hz for peak in peaks])
    assert found.size >= 2, [peak.as_dict() for peak in peaks]
    for target in expected:
        assert float(np.min(np.abs(found - target))) / target < 0.03, (target, found)


def test_a_single_tone_gives_one_peak_with_a_rank_one_shape():
    count = 60_000
    time = np.arange(count) / SAMPLE_RATE_HZ
    signal = np.stack((np.sin(2 * math.pi * 37.0 * time), 0.5 * np.sin(2 * math.pi * 37.0 * time)), axis=1)
    decomposition = spectral_matrix(signal, sample_rate_hz=SAMPLE_RATE_HZ, segment_seconds=8.0,
                                   band=(10.0, 90.0))
    peaks = find_peaks(decomposition, prominence_db=6.0)
    assert peaks, decomposition.as_dict()
    strongest = max(peaks, key=lambda peak: peak.singular_value)
    assert abs(strongest.frequency_hz - 37.0) < 1.5, strongest.as_dict()
    # The two channels carry the same tone at half amplitude, so the shape ratio is 0.5.
    assert 0.4 < strongest.shape_ratio < 0.6, strongest.as_dict()


def test_the_singular_values_are_ordered_at_every_frequency():
    response, _ = _two_dof(seconds=30.0)
    decomposition = spectral_matrix(response, sample_rate_hz=SAMPLE_RATE_HZ, segment_seconds=8.0)
    assert np.all(decomposition.singular_values[1] <= decomposition.singular_values[0] + 1e-12)


def test_refusals_are_specific():
    with pytest.raises(SpectralError) as one_dimensional:
        spectral_matrix(np.zeros(100), sample_rate_hz=SAMPLE_RATE_HZ)
    assert "channels" in str(one_dimensional.value)

    with pytest.raises(SpectralError) as too_long_segment:
        spectral_matrix(np.zeros((500, 2)), sample_rate_hz=SAMPLE_RATE_HZ, segment_seconds=2.0)
    assert "shorten" in str(too_long_segment.value)

    with pytest.raises(SpectralError) as bad_overlap:
        spectral_matrix(np.zeros((4000, 2)), sample_rate_hz=SAMPLE_RATE_HZ, overlap=1.0)
    assert "overlap" in str(bad_overlap.value)

    response, _ = _two_dof(seconds=20.0)
    with pytest.raises(SpectralError) as narrow_band:
        spectral_matrix(response, sample_rate_hz=SAMPLE_RATE_HZ, segment_seconds=8.0, band=(199.0, 199.2))
    assert "four" in str(narrow_band.value)


def test_evidence_travels_with_the_peaks():
    response, _ = _two_dof(seconds=30.0)
    decomposition = spectral_matrix(response, sample_rate_hz=SAMPLE_RATE_HZ, segment_seconds=8.0)
    peaks = find_peaks(decomposition, prominence_db=2.0)
    payload = decomposition.as_dict()
    assert payload["resolution_hz"] > 0.0
    assert payload["segment_seconds"] == 8.0
    for peak in peaks:
        assert peak.prominence_db >= 2.0
        assert 0.0 <= peak.upper_singular_ratio <= 1.0 + 1e-9
        assert len(peak.shape) == 2
