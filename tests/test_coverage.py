"""The held-out coverage test counts what it says it counts, and refuses when it cannot.

Four passes over one track are four measurements of one number, so the wavelength they report is the only
quantity in this project with a genuine out-of-sample fold available.  These tests pin the arithmetic of that
fold -- the prediction width for one new observation, the sign of z, the counting into quarters -- so that a
future change cannot quietly turn a miss into a hit.

Run:  pytest tests/test_coverage.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import s41_coverage as coverage  # noqa: E402

LABELS = ["a.mat", "b.mat", "c.mat", "d.mat"]


def test_prediction_width_is_for_one_new_observation() -> None:
    """s comes from the three training folds only, and the width carries the +1 of a new observation."""
    values = [28.0, 29.0, 26.0, 27.0]
    folds = coverage.prediction_folds(values, LABELS)
    held_out, *train = values
    mean = sum(train) / 3
    spread = math.sqrt(sum((v - mean) ** 2 for v in train) / 2)  # ddof = 1 over three points
    assert folds[0]["train_mean"] == mean
    assert math.isclose(folds[0]["train_spread"], spread, rel_tol=1e-12)
    assert math.isclose(folds[0]["sigma_prediction"], spread * math.sqrt(1.0 + 1.0 / 3.0), rel_tol=1e-12)
    assert folds[0]["n_train"] == 3


def test_the_held_out_value_is_measured_against_its_own_training_folds() -> None:
    """z carries the sign of the residual, and both ends of a drifting set land at the same distance."""
    folds = coverage.prediction_folds([1.00, 1.01, 1.02, 1.03], LABELS)
    assert folds[0]["z"] < 0.0          # 1.00 sits below its training mean of 1.02
    assert folds[3]["z"] > 0.0          # 1.03 sits above its training mean of 1.01
    assert math.isclose(abs(folds[0]["z"]), abs(folds[3]["z"]), rel_tol=1e-12)
    assert math.isclose(abs(folds[0]["z"]), 0.02 / (0.01 * math.sqrt(4.0 / 3.0)), rel_tol=1e-9)
    assert folds[0]["inside_1_sigma"] is False and folds[0]["inside_2_sigma"] is True


def test_a_record_far_from_the_other_three_fails_two_sigma() -> None:
    folds = coverage.prediction_folds([1000.0, 1.0, 1.0, 1.0], LABELS)
    assert folds[0]["inside_2_sigma"] is False
    summary = coverage.summarise(folds)
    assert summary["coverage_2_sigma"] < 1.0
    assert summary["passed"] is False


def test_coverage_can_only_land_on_quarters_with_four_folds() -> None:
    summary = coverage.summarise(coverage.prediction_folds([28.0, 29.0, 26.0, 27.0], LABELS))
    assert summary["folds"] == 4
    for key in ("coverage_1_sigma", "coverage_2_sigma", "coverage_95_interval"):
        assert summary[key] * 4 == pytest_round(summary[key] * 4)


def pytest_round(value: float) -> int:
    return int(round(value))


def test_a_degenerate_training_set_makes_every_offset_infinite_not_a_pass() -> None:
    """Four identical values leave sigma = 0; the fold must not be counted as covered by a zero-width band."""
    summary = coverage.summarise(coverage.prediction_folds([5.0, 5.0, 5.0, 5.0], LABELS))
    assert summary["max_abs_z"] == float("inf")
    assert summary["passed"] is False


def test_the_criterion_needs_both_sigma_levels_and_the_z_limit() -> None:
    covered = {"inside_1_sigma": True, "inside_2_sigma": True, "inside_95": True, "z": 0.5}
    missed_2 = {"inside_1_sigma": False, "inside_2_sigma": False, "inside_95": False, "z": 4.0}
    one_sigma_only = {"inside_1_sigma": False, "inside_2_sigma": True, "inside_95": True, "z": 1.5}
    assert coverage.summarise([covered] * 4)["passed"] is True
    assert coverage.summarise([covered] * 3 + [missed_2])["passed"] is False
    # two of four at one sigma is exactly the bar, so this passes -- the test says where the boundary is
    assert coverage.summarise([covered, covered, one_sigma_only, one_sigma_only])["passed"] is True
    assert coverage.summarise([covered, one_sigma_only, one_sigma_only, one_sigma_only])["passed"] is False


def test_binomial_tail_brackets_the_endpoints() -> None:
    assert math.isclose(coverage.binomial_tail(4, 4, 0.6827), 1.0, rel_tol=1e-12)
    assert math.isclose(coverage.binomial_tail(0, 4, 0.6827), (1.0 - 0.6827) ** 4, rel_tol=1e-12)
    assert coverage.binomial_tail(2, 4, 0.6827) > coverage.binomial_tail(1, 4, 0.6827)
