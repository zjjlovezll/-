"""Tests for the harmonic-ladder inversion.

The claim under test is narrow and falsifiable: *one* run of a periodic short-wave
defect carries as many independent observations of the depth as it has detectable
harmonics, so the depth *shape* can be recovered -- with a sigma -- where a single
band amplitude could only give one number.

Everything here is synthetic: the "measured" response is generated from the model
itself plus noise, so a failure means the algebra is wrong, not that the physics is.
The physics is exercised separately by the scripts that run the solver.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.inverse.harmonics import (
    DepthProfile,
    HarmonicError,
    HarmonicModel,
    calibrate_gains,
    coverage_across_orders,
    harmonic_amplitudes,
    invert_corrugation,
)

PERIOD_M = 0.050
SPEED_M_S = 80.0 / 3.6
FUNDAMENTAL_HZ = SPEED_M_S / PERIOD_M  # 444.4 Hz
GAIN_MAGNITUDE = 26_455.0  # (m/s^2)/m, the measured 80 km/h constant


def _time(seconds: float = 0.25, rate_hz: float = 20_000.0) -> np.ndarray:
    return np.arange(0.0, seconds, 1.0 / rate_hz)


def _truth(orders: dict[int, complex]) -> dict[int, complex]:
    """A model whose gain is the measured constant, with a mild per-order tilt."""

    return dict(orders)


def _model(*orders: int) -> HarmonicModel:
    return HarmonicModel(
        gains={order: GAIN_MAGNITUDE * complex(1.0 - 0.1 * (order - 1), 0.05 * order)
               for order in orders},
        reference_depth_m=30.0e-6,
    )


def test_a_two_harmonic_profile_comes_back_with_the_right_shape() -> None:
    """The whole point: order 2 is recovered separately from order 1."""

    model = _model(1, 2)
    truth = {1: 30.0e-6 + 0.0j, 2: 9.0e-6 * complex(math.cos(0.7), math.sin(0.7))}
    measured = model.predict(truth)

    inverted = invert_corrugation(
        model, measured, measurement_sigma=1e-3, prior_sigma=100e-6,
        fundamental_hz=FUNDAMENTAL_HZ, period_m=PERIOD_M,
    )

    depth = inverted.depth()
    assert depth.coefficients[1] == pytest.approx(truth[1], abs=1e-9)
    assert depth.coefficients[2] == pytest.approx(truth[2], abs=1e-9)


def test_one_band_amplitude_alone_cannot_separate_the_harmonics() -> None:
    """A sanity contrast: with a single order the shape is unidentifiable.

    This is the rank-one situation the band matrix was stuck in.  Two different
    two-harmonic profiles that share their fundamental produce the same one-order
    measurement, so no method can tell them apart -- and the inversion must not
    pretend otherwise: only the fundamental is observed, order 2 stays at the prior.
    """

    model = _model(1, 2)
    shallow = {1: 30.0e-6 + 0.0j, 2: 2.0e-6 + 0.0j}
    deep = {1: 30.0e-6 + 0.0j, 2: 20.0e-6 + 0.0j}
    assert model.predict(shallow)[1] == pytest.approx(model.predict(deep)[1])

    inverted = invert_corrugation(
        model, {1: model.predict(shallow)[1]}, measurement_sigma=1e-3,
        prior_sigma=100e-6, fundamental_hz=FUNDAMENTAL_HZ, period_m=PERIOD_M,
    )
    # Order 2 has no measurement, so its posterior is exactly the prior mean ...
    assert inverted.depth().coefficients[2] == pytest.approx(0.0 + 0.0j)
    # ... and its sigma is the prior, i.e. the answer is explicitly "unknown".
    sigmas = inverted.amplitude_sigma()
    assert sigmas[2] == pytest.approx(100e-6 * math.sqrt(2.0), rel=0.05)
    assert sigmas[1] < sigmas[2]


def test_sigma_per_order_is_the_response_noise_divided_by_that_order_gain() -> None:
    """Each measured order is its own observable: sigma_n = sigma_y / |g_n|.

    This is the property that replaces "more bands, smaller band": the ladder does not
    narrow one number, it adds *independent* numbers, each with the precision its own
    gain allows.  A weak order is therefore honestly less certain, and an unmeasured
    one keeps the prior instead of borrowing another order's precision.
    """

    model = _model(1, 2, 3)
    response_sigma = 2.0e-3
    measured = {order: gain * (30e-6 + 9e-6 + 4e-6) + response_sigma * complex(0.3, -0.2)
                for order, gain in model.gains.items()}
    inverted = invert_corrugation(
        model, measured, measurement_sigma=response_sigma, prior_sigma=100e-6,
        fundamental_hz=FUNDAMENTAL_HZ, period_m=PERIOD_M,
    )
    sigmas = inverted.amplitude_sigma()
    for order, gain in model.gains.items():
        expected = response_sigma / abs(gain) * math.sqrt(2.0)
        assert sigmas[order] == pytest.approx(expected, rel=0.20)
    # Order 3's gain is the smallest of the three, so it must be the least certain.
    assert sigmas[3] > sigmas[2] > sigmas[1]


def test_a_gain_in_the_floor_leaves_that_order_at_the_prior() -> None:
    """Silence at order 3 must not be read as "no depth at order 3"."""

    model = HarmonicModel(
        gains={1: GAIN_MAGNITUDE * 1.0, 2: GAIN_MAGNITUDE * 0.5, 3: 1.0e-6},
        reference_depth_m=30e-6,
    )
    truth = {1: 30e-6 + 0.0j, 2: 8e-6 + 0.0j, 3: 12e-6 + 0.0j}
    measured = model.predict(truth)
    inverted = invert_corrugation(
        model, measured, measurement_sigma=1e-3, prior_sigma=80e-6,
        fundamental_hz=FUNDAMENTAL_HZ, period_m=PERIOD_M, floor_gain=1e-3,
    )
    # Unobserved at order 3: the posterior is the prior mean, and its sigma says "unknown".
    assert inverted.depth().coefficients[3] == pytest.approx(0.0 + 0.0j)
    assert inverted.amplitude_sigma()[3] == pytest.approx(80e-6 * math.sqrt(2.0), rel=0.05)
    # The two live orders are still recovered.
    assert inverted.depth().coefficients[1] == pytest.approx(truth[1], abs=1e-9)


def test_recovered_profile_reproduces_the_waveform_it_came_from() -> None:
    """Compare in the mileage domain, not just coefficient by coefficient."""

    model = _model(1, 2, 3)
    truth = {1: 30e-6 + 0.0j, 2: 8e-6 * complex(math.cos(1.1), math.sin(1.1)),
             3: 3e-6 * complex(math.cos(-0.4), math.sin(-0.4))}
    inverted = invert_corrugation(
        model, model.predict(truth), measurement_sigma=1e-3, prior_sigma=100e-6,
        fundamental_hz=FUNDAMENTAL_HZ, period_m=PERIOD_M,
    )
    reference = DepthProfile(period_m=PERIOD_M, coefficients=truth)
    s = np.linspace(0.0, PERIOD_M, 200)
    worst = float(np.max(np.abs(inverted.depth().at(s) - reference.at(s))))
    assert worst < 1e-9
    assert inverted.peak_to_peak_m() == pytest.approx(reference.peak_to_peak_m, rel=1e-4)


def test_one_sigma_coverage_is_about_sixty_eight_percent() -> None:
    """The BKF criterion: the band must explain the error, not just be small."""

    model = _model(1, 2)
    truth = {1: 30e-6 + 0.0j, 2: 9e-6 + 0.0j}
    clean = model.predict(truth)
    rng = np.random.default_rng(424242)
    sigma_per_amp = 0.10  # 10 % of the line amplitude
    inside = 0
    trials = 200
    for _ in range(trials):
        # Noise proportional to the fundamental line for every order, matching the
        # single measurement_sigma the estimator is told, otherwise the band is wrong.
        scale = sigma_per_amp * abs(clean[1])
        noisy = {order: value + scale * complex(rng.normal(), rng.normal())
                 for order, value in clean.items()}
        inverted = invert_corrugation(
            model, noisy, measurement_sigma=sigma_per_amp * GAIN_MAGNITUDE * 30e-6,
            prior_sigma=100e-6, fundamental_hz=FUNDAMENTAL_HZ, period_m=PERIOD_M,
        )
        rows = coverage_across_orders(inverted, truth)
        inside += sum(1 for row in rows if row["inside"])
    fraction = inside / (trials * 2)
    assert 0.55 < fraction < 0.82, fraction


def test_harmonic_projection_recovers_a_known_two_tone_signal() -> None:
    # Duration chosen so both tones sit on whole periods (50 and 100), otherwise the
    # second harmonic leaks into the first and the comparison is not about the fit.
    time_s = _time(0.1125)
    signal = (26_455.0 * 30e-6 * np.cos(2 * math.pi * FUNDAMENTAL_HZ * time_s + 0.3)
              + 26_455.0 * 9e-6 * np.cos(2 * math.pi * 2 * FUNDAMENTAL_HZ * time_s - 0.8))
    amplitudes = harmonic_amplitudes(time_s, signal, FUNDAMENTAL_HZ, (1, 2))
    assert abs(amplitudes[1]) == pytest.approx(26_455.0 * 30e-6, rel=1e-6)
    assert abs(amplitudes[2]) == pytest.approx(26_455.0 * 9e-6, rel=1e-6)
    assert math.atan2(amplitudes[1].imag, amplitudes[1].real) == pytest.approx(0.3, abs=1e-6)


def test_calibration_learns_the_gain_from_a_known_run() -> None:
    """`calibrate_gains` is the bridge from a measurement to the operator."""

    time_s = _time(0.1125)
    model = _model(1, 2)
    depth = 30e-6
    # Re(g * A e^{i wt}) = A (Re g cos wt - Im g sin wt): the quadrature has to be built
    # into the synthetic signal, otherwise the imaginary part of the gain is unrecoverable
    # and the test would only be checking its real part.
    signal = sum(depth * (gain.real * np.cos(2 * math.pi * order * FUNDAMENTAL_HZ * time_s)
                          - gain.imag * np.sin(2 * math.pi * order * FUNDAMENTAL_HZ * time_s))
                 for order, gain in model.gains.items())
    learned = calibrate_gains(PERIOD_M, depth, SPEED_M_S, time_s, signal)
    for order in (1, 2):
        assert learned.gains[order] == pytest.approx(model.gains[order], rel=5e-3)


def test_refusals_name_the_problem() -> None:
    model = _model(1)
    with pytest.raises(HarmonicError, match="positive"):
        invert_corrugation(model, {}, measurement_sigma=1.0, prior_sigma=1.0,
                           fundamental_hz=0.0, period_m=PERIOD_M)
    with pytest.raises(HarmonicError, match="positive"):
        invert_corrugation(model, {}, measurement_sigma=1.0, prior_sigma=1.0,
                           fundamental_hz=FUNDAMENTAL_HZ, period_m=-1.0)
    with pytest.raises(HarmonicError, match="1-based"):
        HarmonicModel(gains={0: 1.0 + 0.0j}, reference_depth_m=1e-6)
    with pytest.raises(HarmonicError, match="reference depth"):
        HarmonicModel(gains={1: 1.0 + 0.0j}, reference_depth_m=0.0)
    with pytest.raises(HarmonicError, match="equal-length"):
        harmonic_amplitudes([0.0, 1.0], [1.0], 10.0, (1,))
    with pytest.raises(HarmonicError, match="Nyquist"):
        harmonic_amplitudes(np.arange(0.0, 0.001, 1e-4), np.zeros(10), 9000.0, (1,))
    with pytest.raises(HarmonicError, match="1-based"):
        harmonic_amplitudes(np.arange(0.0, 0.01, 1e-4), np.zeros(100), 100.0, (0,))

def test_the_default_floor_keeps_a_negligible_gain_out_of_the_operator() -> None:
    """A gain of 1e-12 must not produce a row: dividing the response noise by it pins that
    harmonic to zero with a sigma of nanometres.  The default floor is relative to the
    largest gain, so callers no longer have to pass one by hand."""

    model = HarmonicModel(
        gains={1: GAIN_MAGNITUDE, 2: 1.0e-12},
        reference_depth_m=30e-6,
    )
    measured = model.predict({1: 30e-6 + 0.0j, 2: 12e-6 + 0.0j})
    inverted = invert_corrugation(
        model, measured, measurement_sigma=1e-3, prior_sigma=80e-6,
        fundamental_hz=FUNDAMENTAL_HZ, period_m=PERIOD_M,
    )
    assert inverted.depth().coefficients[1] == pytest.approx(30e-6, rel=1e-6)
    assert inverted.depth().coefficients[2] == pytest.approx(0.0 + 0.0j)
    assert inverted.amplitude_sigma()[2] == pytest.approx(80e-6 * math.sqrt(2.0), rel=0.05)


def test_a_gain_nobody_can_see_stays_at_the_prior_by_default() -> None:
    """Two percent of the strongest gain is the default floor: silence is not a measurement."""

    model = HarmonicModel(gains={1: complex(10.0, 0.0), 2: complex(0.05, 0.0)},
                          reference_depth_m=30e-6)
    measured = {1: complex(10.0 * 30e-6, 0.0), 2: complex(0.05 * 30e-6, 0.0)}
    inversion = invert_corrugation(model, measured, measurement_sigma=0.01,
                                   prior_sigma=80e-6, fundamental_hz=444.4,
                                   period_m=0.05)
    # Order 1 is measured; order 2 sits under the default floor and must keep the prior width.
    first, second = inversion.orders
    assert first == 1 and second == 2
    assert inversion.posterior.sigma[2] == pytest.approx(80e-6, rel=1e-6)
    assert inversion.posterior.mean[2] == pytest.approx(0.0, abs=1e-9)
