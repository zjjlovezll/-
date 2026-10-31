"""Tests for the joint forward fit: two parameters, the null run as the operating point.

What is pinned here is the arithmetic that took three attempts to get right in round 261:
the bump has to *raise* the predicted share (plus, not minus), the null run has to supply the operating
state instead of the design gap, and the fit has to stay identifiability-limited above the share
saturation rather than silently reporting an amplitude it cannot see.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s124_joint_inversion as joint  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "joint_inversion.json"


@pytest.fixture(scope="module")
def law_parts():
    return joint.assembly.build_law()


def test_the_forward_law_raises_the_share_when_the_blade_rises(law_parts):
    """The sign that was wrong: a bump adds to the operating state and the share must go up."""
    sigma_of = joint.share_law(law_parts)
    state = np.asarray([0.0])
    width = np.asarray([45.19])
    flat = float(sigma_of(state, width)[0])
    raised = float(sigma_of(state + 40.0, width)[0])
    assert raised > flat
    assert raised - flat > 0.05


def test_the_share_saturates_and_that_is_where_the_fit_stops_seeing(law_parts):
    sigma_of = joint.share_law(law_parts)
    width = np.asarray([45.19])
    values = [float(sigma_of(np.asarray([u]), width)[0]) for u in (0.0, 100.0, 200.0)]
    assert values[0] < values[1] < values[2]
    assert values[1] - values[0] > 0.20          # a 100 um raise is well inside the law
    assert values[2] > 0.90                      # 200 um already sits near the top of it
    # Outside the measured window the interpolation clamps to its right value, so a 400 um raise is
    # predicted back at zero share.  That is an extrapolation artefact, and it is why the 100/200 um
    # fits run to their amplitude bound instead of reporting a plausible number.
    beyond = float(sigma_of(np.asarray([400.0]), width)[0])
    assert beyond == pytest.approx(0.0, abs=0.05)


@pytest.mark.corpus
def test_the_joint_fit_recovers_the_small_amplitudes():
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    single = {row["truth_peak_um"]: row for row in payload["modes"]["single"]["amplitudes"]}

    for amplitude in (20.0, 30.0, 40.0, 60.0, 80.0):
        row = single[amplitude]
        assert all(row["gates"].values()), (amplitude, row["gates"])
        assert row["amplitude_relative_pct"] < 2.0
        assert row["p95_um"] < 10.0
        assert row["peak_error_m"] < 0.05


@pytest.mark.corpus
def test_the_joint_fit_reports_its_own_blind_spot():
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    single = {row["truth_peak_um"]: row for row in payload["modes"]["single"]["amplitudes"]}
    multi = {row["truth_peak_um"]: row for row in payload["modes"]["multistart"]["amplitudes"]}

    # 100 and 200 um saturate the share: the fit runs to its amplitude bound and must say so by failing.
    for amplitude in (100.0, 200.0):
        assert single[amplitude]["fit"]["amplitude_um"] > 150.0
        assert single[amplitude]["gates"]["G-ABS"] is False

    assert payload["modes"]["single"]["passing_all_gates"] == 5
    # multi-start lowers the cost but not the error, which is the misspecification finding
    assert multi[80.0]["fit"]["cost"] <= single[80.0]["fit"]["cost"]
    assert multi[80.0]["amplitude_relative_pct"] > single[80.0]["amplitude_relative_pct"]


@pytest.mark.corpus
def test_the_pointwise_assembly_and_the_joint_fit_are_compared_in_the_report():
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    assert "0/3" in payload["finding"]
    assert "5/9" in payload["finding"]
