"""M5 step 3: two more estimators, and the reason all three fail out of range.

Pins the measured failure shapes: the table clamps (peak under-reported), the tanh map amplifies (peak
over-reported) near sigma = 1, and the zero-parameter transfer-station readout under-reports by an
amount that grows with amplitude -- because the gap at which the load halves moves with the amplitude,
which is the branch measured in round 250.
"""
from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "parametric.json"

pytestmark = pytest.mark.corpus


@pytest.fixture(scope="module")
def report() -> dict:
    if not REPORT.is_file():
        pytest.skip(f"no report at {REPORT}")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_every_leave_one_out_fold_fails_gates_and_is_recorded_as_failing(report: dict) -> None:
    rows = report["rows"]
    assert len(rows) == 3
    assert {float(row["held_out_um"]) for row in rows} == {50.0, 100.0, 200.0}
    assert sum(1 for row in rows
               if row["gate_relative"] and row["gate_absolute"] and row["gate_station"]) == 0
    assert "0/3" in report["verdict"]


def test_the_parametrisation_amplifies_near_saturation(report: dict) -> None:
    # The tanh map does not clamp like the table; it over-shoots, which is the opposite failure mode.
    for row in report["rows"]:
        assert row["peak_estimate_m"] > row["peak_true_m"], row
    assert max(row["peak_estimate_m"] / row["peak_true_m"] for row in report["rows"]) > 2.0


def test_the_transfer_station_gap_moves_with_the_amplitude(report: dict) -> None:
    readouts = report["transfer_station"]
    assert len(readouts) == 3
    # z = d(s*) - z_true(s*) is the gap at which the load halves; it must not be treated as a constant
    implied = [row["z_estimate_m"] - row["z_true_m"] for row in readouts]
    assert all(value < 0 for value in implied)
    assert implied[0] > implied[1] > implied[2]          # -27.4, -56.1, -107.4 um
    assert implied[0] < -20e-6 and implied[2] < -100e-6


def test_the_stations_are_still_localised(report: dict) -> None:
    for row in report["transfer_station"]:
        assert abs(row["station_m"] - 58.5) < 1.0
