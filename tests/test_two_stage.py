"""Two stages, and the three-peak profile that no single estimator could do.

Round 274 showed the measured law cannot count peaks (it sizes one bump to 0.45 % but does not compose,
so a free BIC over K picked 5 instead of 3).  Round 275 showed the composable two-body Hertz model counts
correctly (3, with an SSE plateau) but misses even its own calibration bump (share rms 0.1065), so it
sizes the peaks at 16.3 / 27.3 / 15.2 um instead of 40 / 30 / 20.

`scripts/s133_two_stage.py` uses each where it works: count with the composable forward, then size with the
measured law at that fixed count.  Registered before running, both stage-2 variants:

    joint    one least-squares over (A_i, c_i), initialised at the stage-1 peaks
    greedy   measured-law forward selection, stopped at stage-1's count

Every gate is the one from rounds 251/273/274, unchanged.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s133_two_stage as two_stage  # noqa: E402

pytestmark = pytest.mark.corpus

REPORT = two_stage.REPORT


@pytest.fixture(scope="module")
def report() -> dict:
    if not REPORT.exists():
        pytest.skip(f"{REPORT.name} has not been produced yet")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_the_count_comes_from_the_composable_forward(report: dict) -> None:
    """Stage 1 must count three, and its BIC minimum must sit at three."""
    assert report["stage_one"]["selected"] == len(report["truth"]) == 3
    bics = {int(key): value for key, value in report["stage_one"]["bic"].items()}
    assert min(bics, key=bics.get) == 3
    assert bics[4] > bics[3] and bics[5] > bics[3], "the composable forward must plateau after the count"


def test_the_joint_stage_passes_every_gate(report: dict) -> None:
    joint = report["stage_two"]["joint"]
    assert all(joint["gates"].values()), joint["gates"]
    for row in joint["per_peak"]:
        assert row["location_error_m"] <= two_stage.assembly.STATION_LIMIT_M
        assert row["amplitude_relative_pct"] <= two_stage.joint.RELATIVE_LIMIT_PCT
    assert joint["p95_um"] <= two_stage.assembly.ABSOLUTE_LIMIT_UM
    assert len(joint["peaks"]) == 3


def test_the_greedy_variant_is_reported_and_still_fails(report: dict) -> None:
    """The weaker variant must stay in the record; picking it after the fact is what the gates forbid."""
    greedy = report["stage_two"]["greedy"]
    assert not greedy["gates"]["G-ABS"]
    assert greedy["p95_um"] > two_stage.assembly.ABSOLUTE_LIMIT_UM
    assert greedy["p95_um"] > report["stage_two"]["joint"]["p95_um"]


def test_the_verdict_names_the_better_variant(report: dict) -> None:
    assert report["best_by_p95"] == "joint"
    assert "every gate passes" in report["verdict"]


def test_the_stored_peaks_reproduce_the_recorded_gates(report: dict) -> None:
    """Recompute the p95 from the stored peaks so the numbers cannot be hand-written."""
    import s131_peak_count as count_stage

    state = count_stage.observed_state(two_stage.ROUTE)
    for name in ("joint", "greedy"):
        recomputed = two_stage.judge(report["stage_two"][name], state["stations"])
        assert recomputed["p95_um"] == pytest.approx(report["stage_two"][name]["p95_um"], abs=1e-9)
        assert recomputed["gates"] == report["stage_two"][name]["gates"]


def test_the_sizing_keeps_the_documented_operator_level_bias(report: dict) -> None:
    """All three peaks read high, by the same few per cent seen on single bumps (rounds 271/273)."""
    peaks = report["stage_two"]["joint"]["per_peak"]
    assert all(row["amplitude_fit_um"] > row["amplitude_true_um"] for row in peaks)
    over_read = [row["amplitude_relative_pct"] for row in peaks]
    assert max(over_read) < 2.0 and min(over_read) > 0.05


def test_the_stage_two_mask_needs_a_finite_null_operating_point() -> None:
    """Without this the residual is non-finite instead of merely uninformative (a real crash)."""
    state = {"stations": np.array([58.0, 58.1, 58.2]),
             "observed": np.array([0.5, 0.5, 0.5]),
             "u0": np.array([1.0, np.nan, 1.0])}
    assert two_stage._mask(state).tolist() == [True, False, True]
