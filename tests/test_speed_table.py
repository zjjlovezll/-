"""The speed table interpolates, refuses to invent, and reports what it cannot know.

The operator's speed dependence is real (about 32 % from 40 to 80 km/h) but so is its sensitivity to how
the probe rides the corrugation -- the same speed measured through two different probe designs differs by
about a quarter.  These tests pin the arithmetic that survives both facts: interpolation inside the table,
the nearest calibration outside it, and an explicit flag rather than a silent extrapolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import s18_speed_table as table  # noqa: E402

ROWS = [
    {"speed_kmh": 40.0, "gain_per_m": 2.7566e04},
    {"speed_kmh": 50.0, "gain_per_m": 2.3652e04},
    {"speed_kmh": 60.0, "gain_per_m": 2.1937e04},
    {"speed_kmh": 70.8, "gain_per_m": 2.1154e04},
    {"speed_kmh": 80.0, "gain_per_m": 2.0868e04},
]


def test_interpolates_between_the_two_bracketing_measurements() -> None:
    gain, extrapolated, nearest = table.gain_at(55.0, ROWS)
    assert gain == pytest.approx(0.5 * (2.3652e04 + 2.1937e04), rel=1e-12)
    assert extrapolated is False
    assert nearest == pytest.approx(55.0)


def test_returns_the_measured_gain_on_a_table_point() -> None:
    for row in ROWS:
        gain, extrapolated, _ = table.gain_at(float(row["speed_kmh"]), ROWS)
        assert gain == pytest.approx(float(row["gain_per_m"]), rel=1e-12)
        assert extrapolated is False


def test_outside_the_table_reports_the_edge_value_and_says_it_extrapolated() -> None:
    slow, slow_flag, slow_nearest = table.gain_at(25.0, ROWS)
    fast, fast_flag, fast_nearest = table.gain_at(120.0, ROWS)
    assert slow == pytest.approx(2.7566e04)
    assert fast == pytest.approx(2.0868e04)
    assert slow_flag is True and fast_flag is True
    assert slow_nearest == pytest.approx(40.0) and fast_nearest == pytest.approx(80.0)


def test_the_gain_falls_with_speed_so_a_single_number_is_not_speed_blind() -> None:
    """If this ever becomes flat, the whole table stops earning its runtime."""

    gains = [float(row["gain_per_m"]) for row in ROWS]
    assert gains == sorted(gains, reverse=True)
    assert gains[0] / gains[-1] - 1.0 > 0.2
