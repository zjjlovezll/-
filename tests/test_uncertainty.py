"""The posterior has to be checkable, or it is just a wider number.

Every test here pins a property that a paper-grade uncertainty statement needs:
the variance must match the analytic 1x1 answer, it must grow with measurement
noise and shrink with more equations, a transposed operator must not silently
mean something else, and the claimed coverage must actually be observed when
the data are drawn from the model the posterior assumes.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.uncertainty import (
    Posterior,
    UncertaintyError,
    coverage,
    fold_non_negative,
    sigma_from_floor,
    weighted_least_squares,
)


def test_one_unknown_matches_the_analytic_posterior():
    gain, sigma_y, sigma_p = 3.0, 0.5, 10.0
    posterior = weighted_least_squares([[gain]], [gain * 2.0], measurement_sigma=sigma_y,
                                       prior_sigma=[sigma_p], labels=("a",))
    variance = 1.0 / (gain**2 / sigma_y**2 + 1.0 / sigma_p**2)
    mean = variance * gain * (gain * 2.0) / sigma_y**2
    assert posterior.mean[0] == pytest.approx(mean, rel=1e-12)
    assert posterior.sigma[0] == pytest.approx(math.sqrt(variance), rel=1e-12)


def test_sigma_grows_with_measurement_noise_and_falls_without_bound():
    clean = weighted_least_squares([[2.0]], [4.0], measurement_sigma=0.1, prior_sigma=[100.0])
    noisy = weighted_least_squares([[2.0]], [4.0], measurement_sigma=1.0, prior_sigma=[100.0])
    assert noisy.sigma[0] > clean.sigma[0] * 5.0
    # A prior that is wide compared with the data lets sigma shrink without limit.
    tighter = weighted_least_squares([[2.0]], [4.0], measurement_sigma=0.1, prior_sigma=[0.001])
    assert tighter.sigma[0] <= 0.001 + 1e-12


def test_more_equations_narrow_the_band():
    operator = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    sigma_y = [0.2, 0.2, 0.2]
    two = weighted_least_squares(operator[:2], [1.0, 2.0], measurement_sigma=sigma_y[:2],
                                 prior_sigma=[50.0, 50.0])
    three = weighted_least_squares(operator, [1.0, 2.0, 3.0], measurement_sigma=sigma_y,
                                   prior_sigma=[50.0, 50.0])
    assert np.all(three.sigma < two.sigma)
    assert np.allclose(three.mean, [1.0, 2.0], atol=1e-9)


def test_a_transposed_operator_means_the_same_thing():
    # Three responses of two unknowns: the far more common shape here, and the
    # one whose transpose is only unambiguous because the lengths differ.
    operator = np.array([[3.0, 0.5], [0.2, 2.0], [1.0, -1.0]])
    measured = [1.0, 1.0, 0.4]
    rows = weighted_least_squares(operator, measured, measurement_sigma=[0.1, 0.1, 0.1],
                                  prior_sigma=[10.0, 10.0])
    columns = weighted_least_squares(operator.T, measured, measurement_sigma=[0.1, 0.1, 0.1],
                                     prior_sigma=[10.0, 10.0])
    assert np.allclose(rows.mean, columns.mean)
    assert np.allclose(rows.sigma, columns.sigma)


def test_a_silent_equation_leaves_the_prior_in_place():
    posterior = weighted_least_squares([[0.0]], [7.0], measurement_sigma=0.1, prior_sigma=[2.5])
    assert posterior.mean[0] == pytest.approx(0.0, abs=1e-12)
    assert posterior.sigma[0] == pytest.approx(2.5, rel=1e-12)


def test_the_claimed_band_is_observed_on_drawn_data():
    rng = np.random.default_rng(20261026)
    truth = np.array([3.0, -1.5])
    operator = np.array([[1.0, 0.3], [0.1, 1.0], [0.6, -0.4]])
    sigma_y = 0.25
    inside = 0
    entries = 0
    draws = 400
    for _ in range(draws):
        measured = operator @ truth + rng.normal(scale=sigma_y, size=operator.shape[0])
        posterior = weighted_least_squares(operator, measured, measurement_sigma=sigma_y,
                                           prior_sigma=[100.0, 100.0])
        inside += int(np.count_nonzero(np.abs(posterior.z_scores(truth)) <= 1.0))
        entries += truth.size
    # Per coordinate: P(|z| <= 1) = 68.3 %.  Requiring both coordinates at once
    # would only be 46.6 %, which is the mistake this test exists to prevent.
    fraction = inside / entries
    assert 0.60 <= fraction <= 0.77, fraction


def test_coverage_reports_what_it_measured():
    posterior = Posterior(mean=np.array([1.0, 2.0]), covariance=np.diag([0.25, 1.0]),
                          labels=("a", "b"))
    result = coverage(posterior, [1.4, 2.9], k=1.0)
    assert result.inside.tolist() == [True, True]
    assert result.fraction == pytest.approx(1.0)
    assert result.expected == pytest.approx(0.6827, abs=1e-3)
    assert result.worst_z == pytest.approx(0.9, rel=1e-12)
    assert "coverage 100.0 %" in result.describe()


def test_non_negative_folding_zeroes_the_impossible_bands():
    posterior = Posterior(mean=np.array([2.0, -1.0]), covariance=np.diag([0.04, 0.09]),
                          labels=("ok", "negative"))
    folded = fold_non_negative(posterior)
    assert folded.mean.tolist() == [2.0, 0.0]
    # A folded half-normal keeps (1 - 2/pi) of its variance, not all of it: the clamped
    # coordinate is one-sided, so reporting the old sigma would claim certainty.
    assert folded.sigma[1] == pytest.approx(0.3 * math.sqrt(1.0 - 2.0 / math.pi), rel=1e-12)
    assert folded.mean[0] == pytest.approx(2.0)
    assert folded.sigma[0] == pytest.approx(0.2, rel=1e-12)


def test_sigma_from_floor_converts_a_response_into_metres():
    sigma = sigma_from_floor([0.5, 2.0], [10.0, 500.0])
    assert sigma.tolist() == [0.05, 0.004]


def test_bad_inputs_are_refused_with_a_reason():
    with pytest.raises(UncertaintyError, match="prior_sigma must be strictly positive"):
        weighted_least_squares([[1.0]], [1.0], measurement_sigma=0.1, prior_sigma=[0.0])
    with pytest.raises(UncertaintyError, match="measurement_sigma must be strictly positive"):
        weighted_least_squares([[1.0]], [1.0], measurement_sigma=0.0, prior_sigma=[1.0])
    with pytest.raises(UncertaintyError, match="cannot act on"):
        weighted_least_squares(np.zeros((3, 4)), [1.0, 1.0], measurement_sigma=0.1,
                               prior_sigma=[1.0, 1.0])
    with pytest.raises(UncertaintyError, match="labels need"):
        weighted_least_squares([[1.0]], [1.0], measurement_sigma=0.1, prior_sigma=[1.0],
                               labels=("a", "b"))
    with pytest.raises(UncertaintyError, match="k must be finite and positive"):
        Posterior(mean=np.array([1.0]), covariance=np.array([[1.0]]), labels=("a",)).intervals(0.0)
    with pytest.raises(UncertaintyError, match="gain must be strictly positive"):
        sigma_from_floor([1.0], [0.0])
