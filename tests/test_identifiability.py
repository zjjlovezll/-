"""Identifiability analysis: SVD verdicts, dead columns, and the trade-off warning."""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.inverse.identifiability import (
    IdentifiabilityError,
    Sensitivity,
    analyse,
    finite_difference_jacobian,
    normalised_sensitivity,
)


def _sensitivity(jacobian, scales, names=("a", "b")):
    return Sensitivity(names=tuple(names), jacobian=np.asarray(jacobian, dtype=float),
                       scales=tuple(scales))


def test_dead_column_is_unobservable() -> None:
    verdict = analyse(_sensitivity([[1.0, 0.0], [2.0, 0.0]], (1.0, 1.0)))
    assert verdict.identifiable["a"] is True
    assert verdict.identifiable["b"] is False
    assert "no column energy" in verdict.coverage["b"]
    assert verdict.rank == 1


def test_identical_columns_report_trade_off() -> None:
    verdict = analyse(_sensitivity([[1.0, 1.0], [2.0, 2.0]], (1.0, 1.0)))
    assert verdict.rank == 1
    assert math.isinf(verdict.condition_number)
    assert any("trade off" in note for note in verdict.notes)


def test_sensitivity_scales_with_measurement_noise() -> None:
    jacobian = [[1.0], [1.0]]
    tight = normalised_sensitivity(_sensitivity(jacobian, (0.5, 0.5), names=("a",)))
    loose = normalised_sensitivity(_sensitivity(jacobian, (1.0, 1.0), names=("a",)))
    assert tight[0] == pytest.approx(2.0 * loose[0])


def test_weak_column_below_threshold_is_flagged() -> None:
    verdict = analyse(_sensitivity([[1.0, 1.0e-4]], (1.0,)))
    assert verdict.identifiable["b"] is False
    assert "not separable" in verdict.coverage["b"]


def test_zero_sensitivity_is_an_error() -> None:
    with pytest.raises(IdentifiabilityError, match="nothing moves"):
        analyse(_sensitivity([[0.0], [0.0]], (1.0, 1.0), names=("a",)))


def test_finite_difference_is_exact_for_a_linear_model() -> None:
    matrix = np.array([[2.0, -1.0], [0.5, 3.0]])

    def residual(theta: np.ndarray) -> np.ndarray:
        return matrix @ theta + np.array([1.0, -2.0])

    sensitivity = finite_difference_jacobian(residual, [0.3, -0.7], [1e-6, 1e-6])
    assert np.allclose(sensitivity.jacobian, matrix, atol=1e-7)


def test_shape_errors_are_reported() -> None:
    with pytest.raises(IdentifiabilityError, match="columns"):
        Sensitivity(names=("a",), jacobian=np.zeros((2, 3)), scales=(1.0, 1.0))
    with pytest.raises(IdentifiabilityError, match="scales"):
        Sensitivity(names=("a",), jacobian=np.zeros((2, 1)), scales=(1.0,))
    with pytest.raises(IdentifiabilityError, match="non-finite"):
        Sensitivity(names=("a",), jacobian=np.array([[np.nan]]), scales=(1.0,))
    with pytest.raises(IdentifiabilityError, match="positive"):
        finite_difference_jacobian(lambda theta: np.zeros(2), [0.0], [0.0])
