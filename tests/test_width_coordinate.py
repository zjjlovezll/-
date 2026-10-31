"""The contact width is not the missing coordinate.

Round 279 left one explanation standing: the share at a station depends only on a scalar gap.  The most
natural second coordinate is the contact half-width (measured 1.30x change across the transition, and
archived per frame per rail since round 270), so this round tests it properly:

  * the width offset against the un-bumped run only spans -1.47 .. +1.03 mm;
  * the law's residual correlates -0.447 with it on the six-component run (-0.102 on two peaks,
    -0.042 on three);
  * a width correction fitted on the two calibration runs moves the held-out floor 0.1314 -> 0.1193,
    i.e. 9.2 %, six times short of the 0.02 target.

The module also pins the mistake that nearly decided this the wrong way: replacing the empirical law with
a three-parameter logistic makes the base worse than the thing being corrected (0.10 against 0.013 on the
calibration runs), so those numbers are an appendix, not a test.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s137_width_coordinate as width_coordinate  # noqa: E402

pytestmark = pytest.mark.corpus


@pytest.fixture(scope="module")
def report() -> dict:
    if not width_coordinate.REPORT.exists():
        pytest.skip("the width-coordinate test has not been produced yet")
    return json.loads(width_coordinate.REPORT.read_text(encoding="utf-8"))


def test_the_width_dynamic_range_is_small(report: dict) -> None:
    for row in report["rows"]:
        span = row["db_mm_range"][1] - row["db_mm_range"][0]
        assert span < 3.0, row["route"]
        assert row["db_mm_range"][0] < 0.0 < row["db_mm_range"][1]


def test_the_correlation_does_not_support_the_width(report: dict) -> None:
    for row in report["rows"]:
        correlation = row["corr_residual_vs_db"]
        assert correlation is not None
        assert correlation < 0.5, row["route"]
    holdout = next(row for row in report["rows"] if row["route"] == report["holdout"])
    assert holdout["corr_residual_vs_db"] < 0.0, "the sign is negative on the hard profile"


def test_the_held_out_correction_does_not_reach_the_target(report: dict) -> None:
    correction = report["width_correction"]
    assert correction["held_out_floor_before"] == pytest.approx(0.1314, abs=1e-3)
    assert correction["held_out_floor_after"] > 0.10
    assert correction["relative_gain"] < 0.30
    assert correction["reaches_target"] is False


def test_the_verdict_says_the_width_is_not_the_answer(report: dict) -> None:
    verdict = report["verdict"]
    assert "width" in verdict
    assert "not" in verdict or "does not" in verdict
    assert "recovered" not in verdict and "amplitude" not in verdict


def test_the_crude_logistic_is_labelled_as_not_decisive(report: dict) -> None:
    appendix = report["crude_logistic_appendix"]
    assert "cannot decide" in appendix["note"] or "worse base" in appendix["note"]
    # and it must be visibly worse than the law it replaces, which is why it cannot decide
    rows = {row["route"]: row for row in report["rows"]}
    two_peak = next(row for row in appendix["rows"] if row["route"] == "one_set_twopeak")
    assert two_peak["M2_floor"] > 5.0 * rows["one_set_twopeak"]["law_floor"]
