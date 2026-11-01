"""The sampling-density confound is measured away, and stays measured away.

Round 299 left one alternative open for the 16.11 % gap between 80 and 100 km/h: the two runs do not
sample the same nine metres equally densely.  Round 300 decimates the 80 km/h run to the 100 km/h
station step (and coarser) and refits:

    stride 1  11.11 mm  A 66.22 um  centre 58.514 m  p95 6.25 um   usable 369
    stride 2  13.89 mm  A 65.36 um  centre 58.540 m  p95 5.71 um   usable 185
    stride 3  20.83 mm  A 67.15 um  centre 58.489 m  p95 7.16 um   usable 123

The shifts are -0.86 and +0.93 um against a 9.6 um gap, so the pre-registered falsifier (3.0 um)
fires and H1 is rejected.  These tests hold that result: the baseline must keep reproducing, both
shifts must stay inside the tolerance, and the verdict must not drift into claiming the gap is
explained.  They also keep the stride option honest -- it may not silently change the archived
baseline when it is not asked for.
"""

from __future__ import annotations

import sys
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import s153_window_confound as confound  # noqa: E402

pytestmark = pytest.mark.corpus


@pytest.fixture(scope="module")
def measured() -> dict:
    return confound.measure()


def test_the_archived_baseline_is_reproduced_and_decimation_keeps_it_close(measured: dict) -> None:
    baseline = measured[1]["amplitude_um"]
    assert baseline == pytest.approx(66.22, abs=0.05)
    for stride in (2, 3):
        shift = measured[stride]["amplitude_um"] - baseline
        assert abs(shift) < confound.TOLERANCE_UM, (stride, shift)


def test_the_samples_really_are_decimated_so_the_test_matters(measured: dict) -> None:
    # a stride that did not reach the arrays would leave the sample count unchanged and make the
    # whole comparison vacuous
    assert measured[1]["samples"] == 2001
    assert measured[2]["samples"] == 1001
    assert measured[3]["samples"] == 667
    assert measured[2]["station_step_mm"] == pytest.approx(13.89, abs=0.01)


def test_the_verdict_rejects_sampling_and_the_gap_is_the_larger_number(measured: dict) -> None:
    result = confound.verdict(measured)
    assert result["sampling_is_the_explanation"] is False
    assert result["worst_shift_um"] < confound.TOLERANCE_UM
    assert confound.NOTIONAL_GAP_UM > 3 * result["worst_shift_um"]
    assert "REJECTED" not in result["reason"] or "not the explanation" in result["reason"]


def test_a_sampling_artefact_would_have_been_caught(measured: dict) -> None:
    # the falsifier has to be able to fire: an artificial 3.5 um shift is outside the tolerance
    poisoned = {stride: dict(row) for stride, row in measured.items()}
    poisoned[2]["amplitude_um"] = poisoned[1]["amplitude_um"] + 3.5
    assert confound.verdict(poisoned)["sampling_is_the_explanation"] is True


def test_stride_one_is_the_archive_untouched() -> None:
    import s152_cross_speed as cross

    plain = cross.load(cross.RUNS[confound.SPEED_KMH][0], confound.SPEED_KMH, cross.RUNS[confound.SPEED_KMH][2])
    decimated = cross.load(cross.RUNS[confound.SPEED_KMH][0], confound.SPEED_KMH,
                           cross.RUNS[confound.SPEED_KMH][2], stride=2)
    assert len(plain["times"]) == 2 * len(decimated["times"]) - 1
    assert decimated["times"][0] == plain["times"][0]
    assert decimated["times"][1] == plain["times"][2]
    with pytest.raises(SystemExit):
        cross.load(cross.RUNS[confound.SPEED_KMH][0], confound.SPEED_KMH,
                   cross.RUNS[confound.SPEED_KMH][2], stride=0)
