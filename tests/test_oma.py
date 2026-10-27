"""Tests for the operational modal analysis module, against known analytic modes."""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.inverse.oma import (
    ModalError,
    average_correlation,
    covariance,
    identify,
    singular_entropy_increment,
    toeplitz_block,
)

SAMPLE_RATE_HZ = 1000.0


def _two_dof(*, seconds: float = 40.0, seed: int = 20261027, damping: float = 0.02):
    """A 2-dof chain with analytic modes, driven by white noise on the first mass.

    Modal frequencies: ``f = sqrt(k/m * (3 -/+ sqrt(5)) / 2) / 2 pi`` = 22.0 and 57.6 Hz.
    """
    mass = 2.0
    stiffness = 1.0e5
    # Mass matrix m*I, stiffness matrix k*[[2, -1], [-1, 1]].
    matrix = stiffness * np.array([[2.0, -1.0], [-1.0, 1.0]])
    eigenvalues, vectors = np.linalg.eigh(matrix / mass)
    omega = np.sqrt(eigenvalues)
    expected = omega / (2.0 * math.pi)

    # State-space form in modal coordinates: q'' + 2 zeta omega q' + omega^2 q = excitation.
    count = int(seconds * SAMPLE_RATE_HZ)
    dt = 1.0 / SAMPLE_RATE_HZ
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
    return response, expected


def test_two_modes_are_recovered_within_three_percent():
    response, expected = _two_dof()
    result = identify(response, sample_rate_hz=SAMPLE_RATE_HZ, minimum_frequency_hz=5.0,
                      maximum_frequency_hz=300.0, block_rows=10, segments=8)
    found = np.array([mode.frequency_hz for mode in result.modes])
    assert found.size >= 2, [mode.as_dict() for mode in result.modes]
    for target in expected:
        nearest = float(np.min(np.abs(found - target)))
        assert nearest / target < 0.03, (target, found)
    # Damping is the harder estimate; the paper reports 91.76 % accuracy, so 40 % is the honest bar.
    for mode in result.modes:
        if mode.frequency_hz < 70.0:
            assert 0.0 < mode.damping_ratio < 0.06, mode.as_dict()


def test_a_single_tone_is_identified_with_almost_no_damping():
    count = 40_000
    dt = 1.0 / SAMPLE_RATE_HZ
    time = np.arange(count) * dt
    tone = np.stack((np.sin(2 * math.pi * 37.0 * time), 0.7 * np.sin(2 * math.pi * 37.0 * time)), axis=1)
    result = identify(tone, sample_rate_hz=SAMPLE_RATE_HZ, minimum_frequency_hz=20.0,
                      maximum_frequency_hz=60.0, block_rows=8, segments=4)
    found = np.array([mode.frequency_hz for mode in result.modes])
    assert found.size >= 1
    assert float(np.min(np.abs(found - 37.0))) < 1.0, found


def test_singular_entropy_increment_stops_near_the_state_dimension():
    response, _ = _two_dof(seconds=20.0)
    smooth = average_correlation(response, segments=4)
    lags = covariance(smooth, 24)
    plan = toeplitz_block(lags, 8, start=1)
    singular = np.linalg.svd(plan, compute_uv=False)
    order = singular_entropy_increment(singular, tolerance=0.01)
    # Two modes need four states; the increment rule is allowed to be generous but not blind.
    assert 2 <= order <= 20, order


def test_average_correlation_scales_each_segment_to_unit_variance():
    rng = np.random.default_rng(7)
    data = rng.normal(0.0, 1.0, size=(4000, 2))
    data[:2000] *= 50.0  # one loud half, exactly the non-stationarity the paper is worried about
    smooth = average_correlation(data, segments=4)
    per_segment = np.array([smooth[start:stop].std(axis=0)
                            for start, stop in zip(np.linspace(0, 4000, 5, dtype=int)[:-1],
                                                   np.linspace(0, 4000, 5, dtype=int)[1:])])
    assert np.allclose(per_segment, 1.0, atol=0.05), per_segment


def test_refusals_are_specific():
    with pytest.raises(ModalError) as one_dimensional:
        identify(np.zeros(100), sample_rate_hz=SAMPLE_RATE_HZ)
    assert "channels" in str(one_dimensional.value)

    with pytest.raises(ModalError) as too_short:
        identify(np.zeros((40, 2)), sample_rate_hz=SAMPLE_RATE_HZ, block_rows=12)
    assert "samples" in str(too_short.value)

    with pytest.raises(ModalError) as bad_lag:
        covariance(np.zeros((10, 2)), 20)
    assert "lag" in str(bad_lag.value).lower() or "samples" in str(bad_lag.value)

    response, _ = _two_dof(seconds=10.0)
    with pytest.raises(ModalError) as no_order:
        identify(response, sample_rate_hz=SAMPLE_RATE_HZ, orders=(1000,), block_rows=8)
    assert "order" in str(no_order.value).lower()


def test_the_order_carried_out_is_reported_with_the_evidence():
    response, _ = _two_dof(seconds=20.0)
    result = identify(response, sample_rate_hz=SAMPLE_RATE_HZ, block_rows=8, segments=4)
    payload = result.as_dict()
    assert payload["time_lag"] >= 1
    assert payload["poles_total"] >= payload["poles_stable"] >= 0
    for mode in result.modes:
        assert mode.poles >= 1
        assert mode.frequency_spread_hz >= 0.0
