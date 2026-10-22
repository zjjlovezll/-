"""The closed-form quadratic must reproduce ``np.polyfit`` exactly.

It replaces a hot-path call whose result feeds the contact curvature, so an
equivalence test is the only thing that lets the substitution be trusted.
"""

from __future__ import annotations

import numpy as np
import pytest

from velch.contact_law import quadratic_fit


def test_matches_polyfit_on_random_windows() -> None:
    rng = np.random.default_rng(20261020)
    for _ in range(50):
        count = int(rng.integers(5, 80))
        span = float(rng.uniform(5e-4, 1.2e-2))
        t = np.sort(rng.uniform(-span, span, count))
        z = 0.3 - 2.1 * t + 850.0 * t * t + rng.normal(0.0, 1e-7, count)
        assert np.allclose(quadratic_fit(t, z), np.polyfit(t, z, 2), rtol=0, atol=1e-6)


def test_recovers_an_exact_parabola() -> None:
    t = np.linspace(-1e-3, 1e-3, 41)
    z = 1e-3 * (1.0 - (t / 1e-3) ** 2)
    a2, a1, a0 = quadratic_fit(t, z)
    assert a2 == pytest.approx(-1e3, rel=1e-12)
    assert a1 == pytest.approx(0.0, abs=1e-12)
    assert a0 == pytest.approx(1e-3, rel=1e-12)


def test_needs_three_points() -> None:
    with pytest.raises(ValueError):
        quadratic_fit(np.array([0.0, 1e-3]), np.array([0.0, 0.0]))


def test_rejects_mismatched_sizes() -> None:
    with pytest.raises(ValueError):
        quadratic_fit(np.zeros(4), np.zeros(3))
