"""The model-based inversion is reported as failing, and these tests pin down how.

The point of the tests is not to celebrate a failure but to freeze the shape of it: which folds over-read,
which under-read, and that the fitted stiffness stayed physical.  If a later change makes this family pass,
these tests should be rewritten deliberately rather than deleted by accident.
"""
from __future__ import annotations

import json
import pathlib

import pytest

REPORT = (pathlib.Path(__file__).resolve().parents[1] / "reports"
          / "load_split_inversion_2026-10-31" / "model.json")

pytestmark = pytest.mark.corpus


@pytest.fixture(scope="module")
def report() -> dict:
    if not REPORT.exists():
        pytest.skip(f"{REPORT} has not been generated on this machine")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_the_fitted_stiffness_stays_in_the_physical_range(report: dict) -> None:
    # The frozen contact stiffness is 1.1267e11 N/m^1.5; a fit that leaves the range 2e10..6e11 would mean
    # the model is absorbing something other than contact stiffness.
    assert len(report["rows"]) == 3
    for row in report["rows"]:
        assert 2.0e10 <= row["c_stock"] <= 6.0e11, row
        assert 2.0e10 <= row["c_blade"] <= 6.0e11, row


def test_no_held_out_amplitude_passes_all_three_gates(report: dict) -> None:
    passing = [row for row in report["rows"]
               if row["gate_relative"] and row["gate_absolute"] and row["gate_station"]]
    assert passing == [], passing
    assert report["verdict"].startswith("the model-based inversion passes all three gates on 0/3")


def test_the_family_compresses_the_amplitude_scale(report: dict) -> None:
    # Small bumps are over-read, large ones under-read: that is the compression the support compliance would
    # explain, so the direction has to be recorded rather than left to memory.
    by_held = {row["held_out_um"]: row for row in report["rows"]}
    small = by_held[50.0]
    large = by_held[200.0]
    assert small["peak_estimate_m"] > 1.5 * small["peak_true_m"], small
    assert large["peak_estimate_m"] < 1.0 * large["peak_true_m"], large


def test_localisation_survives_every_fold(report: dict) -> None:
    # The station of the inverted peak is the one thing all four estimator families got right.
    for row in report["rows"]:
        assert abs(row["peak_station_m"] - 58.5) <= 0.52, row
