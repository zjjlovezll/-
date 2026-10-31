"""The round-277 floor is real non-composition, not the law's u-range clamping.

Round 277 attributed the random-profile failure to the forward model on the strength of one number
(share rms 0.1314).  That number has a twin explanation -- the law is a clamped lookup, so a large raise
can leave its range and be answered with a saturated share.  This round separates them with no new
simulation, and this module pins the result:

  * the truth stays inside the measured u-range (clamped fraction 0.0 %) on all three runs;
  * the floor recomputed over in-range stations is bit-identical to the round-277 number;
  * the floor grows with the number of superposed components (0.0133 -> 0.0427 -> 0.1314), which is the
    signature of a per-station-independent assumption failing, not of a single out-of-range station.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s135_floor_diagnosis as diagnosis  # noqa: E402

pytestmark = pytest.mark.corpus


@pytest.fixture(scope="module")
def report() -> dict:
    if not diagnosis.REPORT.exists():
        pytest.skip("the floor diagnosis has not been produced yet")
    return json.loads(diagnosis.REPORT.read_text(encoding="utf-8"))


def test_the_floor_is_not_a_range_artefact(report: dict) -> None:
    for row in report["runs"]:
        assert row["clamped_fraction"] == 0.0, row["route"]
        assert row["clamped_low"] == 0 and row["clamped_high"] == 0
        assert row["unclamped"] == row["usable"]
        assert row["floor_unclamped"] == pytest.approx(row["floor_all"], abs=1e-12)


def test_the_floor_grows_with_the_number_of_components(report: dict) -> None:
    by_route = {row["route"]: row["floor_all"] for row in report["runs"]}
    two = by_route["one_set_twopeak"]
    three = by_route["one_set_threepeak_obs"]
    six = by_route["one_set_random"]
    assert two < three < six
    assert three / two > 1.5, "three components must be measurably worse than two"
    assert six / three > 1.5, "six components must be measurably worse than three"


def test_the_two_peak_floor_agrees_with_round_274(report: dict) -> None:
    """Round 274 measured 0.0165 for the two-peak superposition with its own operating point."""
    by_route = {row["route"]: row["floor_all"] for row in report["runs"]}
    assert by_route["one_set_twopeak"] == pytest.approx(0.0165, abs=0.006)


def test_the_verdict_does_not_claim_a_mechanism(report: dict) -> None:
    verdict = report["verdict"]
    assert "not a range artefact" in verdict
    assert "clamping" in verdict or "range" in verdict
    # a diagnosis may not quietly turn into a result about amplitudes
    assert "recovered" not in verdict


def test_the_random_truth_used_here_is_the_one_that_was_simulated() -> None:
    import s134_random_profile as random_profile

    stations = np.asarray([58.801, 59.257, 60.077, 60.856, 61.354, 61.987])
    peaks = random_profile.truth_peaks()
    values = diagnosis._random_profile(stations)
    expected = sum(amplitude * np.exp(-0.5 * ((stations - centre) / random_profile.WIDTH_M) ** 2)
                   for centre, amplitude in peaks)
    assert np.allclose(values, expected, rtol=0.0, atol=1e-9)
