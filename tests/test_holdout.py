"""Tests for the M7 hold-outs: one amplitude and one position the estimators never saw.

The point of these tests is to keep the negative result negative.  Round 261's 5/9 was measured on the
runs that tuned it; these two cases are outside that set, and the numbers they produced (a hybrid that
clears the absolute gate but not the relative one, and a position shift that breaks both estimators)
must not drift toward the flattering reading.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s125_holdout as holdout  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "holdout.json"


def test_the_onset_station_is_the_first_crossing_not_the_peak():
    stations = np.linspace(57.0, 60.0, 31)
    share = np.zeros_like(stations)
    share[stations >= 58.2] = 0.90
    share[stations >= 58.5] = 1.00          # the peak plateaus from 58.5 on
    assert holdout._onset_station(stations, share) == pytest.approx(58.5, abs=0.11)
    empty = np.zeros_like(stations)
    assert np.isnan(holdout._onset_station(stations, empty))


def test_the_scorer_is_exact_when_the_estimate_is_the_truth():
    stations = np.linspace(56.0, 62.0, 500)
    truth = 100.0 * np.exp(-0.5 * ((stations - 58.5) / holdout.SIGMA_M) ** 2)
    row = holdout._score(truth, stations, 100.0, 58.5)
    assert row["p95_um"] == pytest.approx(0.0, abs=1e-9)
    assert row["worst_bin_relative_pct"] == pytest.approx(0.0, abs=1e-9)
    assert row["peak_error_m"] == pytest.approx(0.0, abs=1e-9)
    assert all(row["gates"].values())


@pytest.mark.corpus
def test_the_amplitude_hold_out_splits_between_the_two_gates():
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    row = payload["holdouts"][0]
    assert row["label"] == "h-a-150um-c58.5"

    # share-only saturates and runs to the amplitude bound: 249 um, not a number anyone can use
    assert row["share_only"]["amplitude_um"] > 300.0
    assert row["share_only"]["gates"]["G-ABS"] is False

    # the onset-station hybrid reaches the absolute gate (16 um against 22) but misses the relative one
    assert row["hybrid"]["gates"]["G-ABS"] is True
    assert row["hybrid"]["p95_um"] == pytest.approx(16.0, abs=2.0)
    assert row["hybrid"]["gates"]["G-REL"] is False
    assert row["hybrid"]["worst_bin_relative_pct"] > 2.0


@pytest.mark.corpus
def test_the_position_hold_out_breaks_both_estimators():
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    row = payload["holdouts"][1]
    assert row["label"] == "h-b-100um-c59.5"
    for name in ("share_only", "hybrid"):
        assert not any(row[name]["gates"].values()), name
        assert row[name]["peak_error_m"] > 0.20
    assert payload["share_only_passes"] == 0
    assert payload["hybrid_passes"] == 0
    assert "0/2" in payload["verdict"]
