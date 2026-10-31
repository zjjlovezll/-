"""The static split at a station is the rolling split there, to a median of 0.0022.

Round 283 closed the closed-form contact families, so the only remaining route to a composable forward is
to ask the solver station by station.  Before paying for 300 stations, this probe asks whether a *seated*
answer is even the right quantity: park the axle on a station, seat, and compare with the split the rolling
run reports at that same station.

Measured: 9/10 probes within 0.02 (median 0.0022, worst 0.0218 at 61.0 m), and six single-body branches that
are physical (the blade carries nothing at 52-58 m; the stock lifts off at 58.5 m with a 100 um raise).

What it does *not* show: that the response to a raise has the same slope as during rolling.  That is the
next question and it costs a time-domain run per raise, not a seat.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "solver_calibration.json"


@pytest.fixture(scope="module")
def report() -> dict:
    if not REPORT.exists():
        pytest.skip("the calibration probe has not been produced yet")
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.mark.corpus
def test_every_probe_converges_and_the_single_body_branches_are_named(report: dict) -> None:
    rows = report["rows"]
    assert rows
    assert all(row["residual_n"] <= 1.0e-5 for row in rows)
    # a single live contact is a physical branch here, not a failed solve; it must be counted, not hidden
    single = [row for row in rows if row["active"] == 1]
    assert len(single) == report["single_body_probes"]
    assert len(single) >= 1
    assert all(row["share_seated"] in (0.0, 1.0) for row in single)


@pytest.mark.corpus
def test_the_seated_split_tracks_the_rolling_split(report: dict) -> None:
    comparisons = report["comparisons"]
    assert len(comparisons) == 10
    diffs = sorted(item["abs_diff"] for item in comparisons)
    median = 0.5 * (diffs[4] + diffs[5])
    assert median <= 0.005, median
    assert report["within_tolerance"] >= 9
    # the worst station misses the 0.02 gate by less than a thousandth; that is recorded, not rounded away
    assert 0.02 < report["worst_abs_diff"] <= 0.03
    assert report["r2"] is False


@pytest.mark.corpus
def test_the_flat_part_of_the_ramp_reproduces_exactly(report: dict) -> None:
    flat = [item for item in report["comparisons"] if item["station_m"] <= 58.0]
    assert len(flat) == 5
    assert all(item["share_seated"] == 0.0 for item in flat)
    assert all(item["abs_diff"] == 0.0 for item in flat)


@pytest.mark.corpus
def test_the_sensitivity_is_positive_and_of_one_sign(report: dict) -> None:
    slopes = [item["slope_per_m"] for item in report["sensitivities"]]
    assert len(slopes) == 3
    assert all(slope > 0 for slope in slopes)
    # 0.0038 .. 0.0047 share per micrometre
    assert all(3.0e3 < slope < 5.5e3 for slope in slopes)
    assert report["r3"] is True


@pytest.mark.corpus
def test_the_verdict_does_not_claim_the_slope(report: dict) -> None:
    verdict = report["verdict"]
    assert "tracks the rolling split" in verdict
    assert "error budget" in verdict
    for banned in ("recovered", "amplitude", "slope matches"):
        assert banned not in verdict
