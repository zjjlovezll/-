"""Pin the engage-reference arithmetic: the crown-gap split is exact for touch, insufficient for 5 %.

Every number here was measured on 2026-11-01 and is quoted in
``docs/ENGAGE_REFERENCE_2026-11-01.md``.  The tests deliberately separate the three claims:

* the law is built from the frozen oracle and this case's own weight, with nothing fitted;
* the crown gap reproduces the calibrated touch station exactly, so it *is* the quantity the solver
  sees for first contact;
* the same gap does **not** reproduce the 5 % share, so the reference station must come from the
  contact geometry.  The last item is the one that would quietly turn a suspended gate into a
  passing one if it were allowed to drift.
"""

from __future__ import annotations

import sys
import pathlib

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import s157_engage_reference as engage  # noqa: E402


@pytest.fixture(scope="module")
def row() -> dict:
    measured = engage.measure()
    measured["verdict"] = engage.verdict(measured)
    return measured


def test_stiffness_is_the_frozen_oracle_and_nothing_else() -> None:
    stiffness = engage.stiffness_n_m_1p5()
    assert stiffness == pytest.approx(1.12670e11, rel=1e-4)
    # The law has to reproduce the oracle it was calibrated on: one surface alone at the frozen force.
    load = engage.FROZEN_FORCE_N
    depth = (load / stiffness) ** (2.0 / 3.0)
    assert depth * 1e6 == pytest.approx(65.4661, rel=1e-6)


def test_split_is_symmetric_at_zero_gap_and_falls_monotonically() -> None:
    assert engage.share_of(0.0) == pytest.approx(0.5, abs=1e-9)
    gaps = [0.0, 10e-6, 20e-6, 30e-6, 40e-6, 50e-6, 60e-6, 70e-6]
    shares = [engage.share_of(gap) for gap in gaps]
    assert all(a > b for a, b in zip(shares, shares[1:])), shares
    assert shares[-1] == pytest.approx(0.0, abs=1e-12)


def test_crown_gap_reproduces_the_calibrated_touch_station(row: dict) -> None:
    # This is the claim that makes the comparison fair: touch is decided by the highest point.
    assert row["touch_mismatch_m"] <= engage.GEOMETRY_TOLERANCE_M
    assert row["touch_station_geometry_m"] == pytest.approx(57.733, abs=0.02)


def test_five_percent_reference_falls_short_and_the_verdict_says_so(row: dict) -> None:
    assert row["gap_for_5pct_um"] == pytest.approx(54.66, abs=0.30)
    assert row["station_law_5pct_m"] == pytest.approx(57.853, abs=0.010)
    assert row["station_model_5pct_m"] == pytest.approx(58.156, abs=0.005)
    assert row["station_offset_m"] == pytest.approx(0.303, abs=0.010)
    assert row["station_offset_m"] > engage.TOLERANCE_M
    assert row["verdict"]["crown_gap_split_sufficient"] is False
    assert row["verdict"]["geometry_reproduces_touch"] is True
    assert row["verdict"]["offset_within_tolerance"] is False


def test_effective_gap_excess_is_what_the_next_step_must_explain(row: dict) -> None:
    # The model needs the blade to look ~28 um lower than its crown says before it reports 5 %.
    assert row["crown_gap_at_model_um"] == pytest.approx(26.45, abs=0.30)
    assert row["effective_gap_excess_um"] == pytest.approx(28.2, abs=0.50)
    # And the two are the same statement, so a typo in one cannot pass unnoticed.
    assert row["effective_gap_excess_um"] == pytest.approx(
        row["gap_for_5pct_um"] - row["crown_gap_at_model_um"], abs=1e-6
    )
