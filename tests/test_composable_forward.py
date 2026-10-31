"""A forward model that composes: the peak count comes right, the amplitudes do not.

Round 274's count failed because the measured share law does not compose (rms 0.0317 fed the truth).
This round swaps in a two-body Hertz split -- which composes by construction -- with its two stiffnesses
fitted on the single 50 um bump and never on the profile under test.

What happens is worth pinning exactly:

  * the mode selection now stops at K = 3 (truth), i.e. G-COUNT passes and the BIC has a minimum at 3
    with the SSE plateauing there (2.21 -> 2.20 -> 2.20);
  * the amplitudes do not: p95 23.56 um (gate 22), amplitudes 16.3 / 27.3 / 15.2 um against 40 / 30 / 20,
    and the model misses even its own calibration bump (share rms 0.1065).

So counting and sizing came apart: counting was a superposition problem, sizing is a forward-accuracy
problem.  These tests keep both halves visible -- a future change that makes the amplitudes pass must not
be able to hide that it also changed the count.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

pytestmark = pytest.mark.corpus

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "composable_forward.json"
LAW = ROOT / "reports" / "load_split_inversion_2026-10-31" / "peak_count.json"


@pytest.fixture(scope="module")
def report() -> dict:
    assert REPORT.is_file(), f"missing {REPORT}; run scripts/s132_composable_forward.py --report"
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_the_two_stiffnesses_are_physical_and_their_own_fit_is_crude(report):
    stiffness = report["stiffness"]
    assert 2.0e9 <= stiffness["c_stock"] <= 6.0e11
    assert 2.0e9 <= stiffness["c_blade"] <= 6.0e11
    # the model misses the very bump it was calibrated on -- that cap is what limits the amplitudes
    assert 0.05 <= stiffness["share_rms_on_calibration"] <= 0.15


def test_the_count_comes_right_with_a_composable_forward(report):
    three = report["three_peak"]
    assert three["selected_count"] == 3
    assert three["gates"]["G-COUNT"] is True
    bic = {int(key): value for key, value in three["bic"].items()}
    assert min(bic, key=bic.get) == 3


def test_the_residual_plateaus_at_the_true_count(report):
    cost = {int(key): value for key, value in report["three_peak"]["cost"].items()}
    assert cost[3] < cost[2] < cost[1]
    # adding a fourth kernel buys less than 5 % of what the first three bought
    assert (cost[3] - cost[4]) < 0.05 * (cost[1] - cost[3])


def test_the_amplitudes_still_fail_and_that_is_reported(report):
    three = report["three_peak"]
    assert three["gates"]["G-ABS"] is False
    assert 22.0 < three["p95_um"] < 30.0
    assert three["gates"]["G-LOC"] is False  # one peak sits 0.200 m away, exactly on the gate
    assert report["verdict"].startswith("the composable forward still does not count")


def test_the_composable_forward_composes_worse_than_the_law_but_counts_better(report):
    """The two claims are independent and both are measured: accuracy vs behaviour under superposition."""
    law = json.loads(LAW.read_text(encoding="utf-8"))
    composable = report["composition"]["three_peak"]["share_rms"]
    measured_law = law["composition"]["one_set_threepeak_obs"]["share_rms"]
    assert composable > 3.0 * measured_law
    assert law["three_peak"]["selected_count"] == 5
    assert report["three_peak"]["selected_count"] == 3


def test_the_forward_responds_in_the_right_direction():
    """Pure check on the model itself: raising the blade raises its share, lowering it lowers it."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import s132_composable_forward as forward

    load = np.array([60.0e3])
    share_mid = forward.share_model(np.array([0.0]), load, 8.4e10, 9.7e10)[0]
    share_blade_up = forward.share_model(np.array([-40e-6]), load, 8.4e10, 9.7e10)[0]
    share_blade_down = forward.share_model(np.array([40e-6]), load, 8.4e10, 9.7e10)[0]
    assert share_mid > 0.2
    assert share_blade_up > share_mid
    assert share_blade_down < share_mid
