"""A2: the implicit-derivative slope of the series contact spring.

`series_normal_force` finds N by five Newton steps, so its own finite difference
carries a staircase from the iteration count. `series_normal_force_slope` gets the
derivative from the implicit relation instead. These tests pin the two against
each other, which is the only check the closed form can have on its own.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.support_compliance import series_normal_force, series_normal_force_slope

C = 1.1393229166e11  # effective_modulus * sqrt(effective_radius), the production law
G = 2.0e-8           # support compliance, m/N - the order the layered track produces


def _central(depth: float, step: float, stiffness: float, compliance: float | None) -> float:
    return ((series_normal_force(depth + step, stiffness, compliance)
             - series_normal_force(depth - step, stiffness, compliance)) / (2.0 * step))


@pytest.mark.parametrize("depth", np.linspace(5.0e-6, 5.0e-4, 20))
def test_slope_matches_central_difference_with_compliance(depth: float) -> None:
    depth = float(depth)
    analytic = series_normal_force_slope(depth, C, G)
    reference = _central(depth, depth * 1.0e-4, C, G)
    assert analytic > 0.0
    assert abs(analytic - reference) / analytic < 1.0e-8


@pytest.mark.parametrize("depth", np.linspace(5.0e-6, 5.0e-4, 20))
def test_slope_matches_hertz_closed_form(depth: float) -> None:
    depth = float(depth)
    analytic = series_normal_force_slope(depth, C, None)
    assert analytic == pytest.approx(1.5 * C * math.sqrt(depth), rel=1.0e-12)
    reference = _central(depth, depth * 1.0e-4, C, None)
    assert abs(analytic - reference) / analytic < 1.0e-8


def test_compliance_softens_the_slope() -> None:
    depth = 6.5e-5
    hertz = series_normal_force_slope(depth, C, None)
    compliant = series_normal_force_slope(depth, C, G)
    assert 0.0 < compliant < hertz


def test_below_the_knee_the_force_and_slope_are_both_zero() -> None:
    """At and below contact the force is zero and the slope is reported as zero."""
    for depth in (-1.0e-4, -1.0e-12, 0.0):
        assert series_normal_force_slope(depth, C, G) == 0.0
        assert series_normal_force(depth, C, G) == 0.0
    # Just above contact the two laws differ by orders of magnitude in slope:
    # Hertz starts from zero, a compliant support starts from the support slope.
    assert series_normal_force_slope(1.0e-12, C, G) > 0.0


def test_slope_grows_monotonically_with_depth() -> None:
    slopes = [series_normal_force_slope(float(depth), C, G)
              for depth in np.linspace(1.0e-6, 5.0e-4, 40)]
    assert all(later > earlier for earlier, later in zip(slopes, slopes[1:]))


def test_invalid_stiffness_is_rejected_only_on_the_compliant_branch() -> None:
    with pytest.raises(ValueError):
        series_normal_force_slope(1.0e-4, 0.0, G)
