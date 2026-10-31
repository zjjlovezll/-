"""A per-station two-body point-Hertz model (no fitted stiffness) misses even the null run.

The model derives each body's contact stiffness from its own crown curvature and solves
F_stock + F_blade = half load per station.  Its floors are 0.31 / 0.32 / 0.41 / 0.51 with a -0.22 bias,
i.e. worse than the calibration-fitted empirical law and failing the un-bumped run too, so the failure is
not "composition" but the absolute split -- and the mechanism is visible in R_blade, which falls to 1 mm
at the narrow sections while C goes as sqrt(R*).  A point-contact size law makes the blade look like a
knife; the real contact there is conformal along the rolling direction.

This module pins the outcome and the sign convention that produced a false "flat" model on the first run.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s138_two_body_station as station_model  # noqa: E402


class _Profile:
    """A parabola open downwards, i.e. a crown of radius R and apex at y = 0."""

    def __init__(self, radius: float, points: int = 2001, half_width: float = 0.04) -> None:
        self.y_m = np.linspace(-half_width, half_width, points)
        self.z_m = -(self.y_m ** 2) / (2.0 * radius)


def test_the_crown_radius_uses_the_absolute_curvature() -> None:
    for radius in (0.3, 0.05, 1.0):
        measured = station_model._curvature_radius(_Profile(radius), half_window=5.0e-3)
        assert measured == pytest.approx(radius, rel=0.02), radius


def test_a_flat_surface_reports_no_radius() -> None:
    profile = _Profile(1.0)
    profile.z_m = np.zeros_like(profile.z_m)
    assert station_model._curvature_radius(profile) == float("inf")


@pytest.mark.corpus
def test_the_station_model_still_misses_the_floor() -> None:
    if not station_model.REPORT.exists():
        pytest.skip("the two-body station test has not been produced yet")
    report = json.loads(station_model.REPORT.read_text(encoding="utf-8"))
    rows = {row["route"]: row for row in report["rows"]}

    # the sections are what the model reads: crowns of 299-300 mm, and a blade edge down to ~1 mm
    assert 0.29 < report["R_stock_mm_range"][0] / 1e3 < 0.31
    assert report["R_blade_mm_range"][0] < 5.0

    # the un-bumped run must be the first thing it gets right, and it is not
    null = rows["straight_one_set"]
    assert null["floor"] > 0.10
    assert null["bias"] < -0.10
    for name, row in rows.items():
        assert row["floor"] > 0.10, name
        assert row["bias"] < -0.15, name
    assert report["all_bumped_runs_pass"] is False


@pytest.mark.corpus
def test_the_verdict_does_not_claim_success() -> None:
    if not station_model.REPORT.exists():
        pytest.skip("the two-body station test has not been produced yet")
    report = json.loads(station_model.REPORT.read_text(encoding="utf-8"))
    verdict = report["verdict"]
    assert "still misses" in verdict
    assert "recovered" not in verdict and "amplitude" not in verdict
