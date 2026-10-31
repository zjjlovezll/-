"""The floor is not interpolation resolution either.

Round 278 ruled out the clamped-lookup explanation and left the mechanism open.  The cheapest remaining
candidate was resolution: the measured share law is a seven-knot lookup, and a profile with more
components might put more stations between knots, where linear interpolation crosses a curved segment.

That hypothesis predicts two things, and neither holds:

  P1  the six-component profile sits in the steep band more often than the two-peak one -- measured 100 %
      on every run, so there is no such difference;
  P2  within a run |error| grows with the distance to the nearest knot -- measured correlation 0.479 on
      the six-component run (below the 0.5 threshold) and -0.282 on the two-peak run (the wrong sign).

This module pins both, and pins the exclusion table so a later round cannot quietly re-propose a
candidate that was already measured away.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s136_law_resolution as resolution  # noqa: E402

pytestmark = pytest.mark.corpus

KNOT_U = (-200.0, -100.0, -50.0, 0.0, 50.0, 100.0, 250.0)


@pytest.fixture(scope="module")
def report() -> dict:
    if not resolution.REPORT.exists():
        pytest.skip("the law-resolution diagnosis has not been produced yet")
    return json.loads(resolution.REPORT.read_text(encoding="utf-8"))


def test_the_knots_are_the_seven_station_sweep_offsets(report: dict) -> None:
    assert tuple(float(value) for value in report["knots_u"]) == pytest.approx(KNOT_U)
    sigma = np.asarray(report["knots_sigma"], dtype=float)
    # Share rises with the raise (a raised blade takes more load -- round 274's sign measurement), so the
    # knots must be monotone increasing once sorted by u.
    assert np.all(np.diff(sigma) >= -1e-12), "the knots must be monotone in the raise"


def test_neither_prediction_held(report: dict) -> None:
    assert report["p1_steep_fraction"] is False
    assert report["p2_error_vs_knot_distance"] is False
    assert "neither prediction holds" in report["verdict"]
    assert "per-station assumption" in report["verdict"]


def test_the_runs_all_sit_in_the_steep_band(report: dict) -> None:
    for row in report["runs"]:
        assert row["steep_fraction"] == pytest.approx(1.0), row["route"]


def test_the_knot_distance_distribution_is_the_same_across_profiles(report: dict) -> None:
    """If the spacing were the explanation, these would have to differ; they do not."""
    by_route = {row["route"]: row for row in report["runs"]}
    two = by_route["one_set_twopeak"]
    six = by_route["one_set_random"]
    assert abs(six["nearest_knot_p90_um"] - two["nearest_knot_p90_um"]) < 5.0
    assert six["floor_um_share"] / two["floor_um_share"] > 5.0


def test_the_correlation_does_not_support_resolution(report: dict) -> None:
    by_route = {row["route"]: row["corr_error_vs_knot_distance"] for row in report["runs"]}
    assert by_route["one_set_random"] < 0.5
    assert by_route["one_set_twopeak"] < 0.0


def test_the_verdict_gives_no_amplitude(report: dict) -> None:
    assert "recovered" not in report["verdict"]
    assert "amplitude" not in report["verdict"]
