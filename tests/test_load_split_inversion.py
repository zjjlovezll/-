"""M5 step 2: the load split inverts a station-resolved bump only inside its calibration range.

The report is produced by ``scripts/s113_profile_inversion.py`` from the four archived 0.6 s runs.  It
is committed under ``reports/load_split_inversion_2026-10-31/``; the run archives are not versioned, so
this test skips -- rather than passing silently -- when the report is absent.

Two facts are pinned, and they pull in opposite directions on purpose:

* inside the calibration range the inversion is good (50 um: peak +13.7 %, p95 15 um, station 0.14 m);
* outside it the estimator clamps to the edge of its table and under-recovers by 23 % and 49 %.

The second one is the reason the next inversion has to be parametrised by amplitude rather than tabulated
from one amplitude's samples.
"""
from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "inversion.json"

pytestmark = pytest.mark.corpus


@pytest.fixture(scope="module")
def report() -> dict:
    if not REPORT.is_file():
        pytest.skip(f"no report at {REPORT}")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _row(report: dict, amplitude: float) -> dict:
    for row in report["rows"]:
        if abs(float(row["amplitude_um"]) - amplitude) < 1e-9:
            return row
    raise AssertionError(f"no row for {amplitude} um")


def test_inside_the_calibration_range_the_inversion_meets_all_three_gates(report: dict) -> None:
    row = _row(report, float(report["calibration_um"]))
    assert row["gate_relative"] and row["gate_absolute"] and row["gate_station"]
    assert row["p95_error_m"] <= 22e-6
    assert abs(row["peak_station_m"] - 58.5) <= 0.20


def test_outside_it_the_estimator_under_recovers_monotonically(report: dict) -> None:
    holdout = [row for row in report["rows"] if float(row["amplitude_um"]) != float(report["calibration_um"])]
    assert len(holdout) == 2
    for row in holdout:
        # the estimate never reaches the truth, and never reaches it by a little
        assert row["peak_estimate_m"] < row["peak_true_m"]
        assert row["p95_error_m"] > 22e-6
        assert not row["gate_absolute"]
    recovered = [row["peak_estimate_m"] / row["peak_true_m"] for row in report["rows"]]
    # more bump is still read as more bump, but with diminishing return
    assert recovered[0] > recovered[1] > recovered[2]


def test_the_pre_registered_gates_are_the_ones_that_were_run(report: dict) -> None:
    gates = report["gates"]
    assert gates["relative_limit"] == 0.02
    assert gates["absolute_limit_m"] == 22e-6
    assert gates["station_limit_m"] == 0.20
    assert gates["floor_m"] == 0.5e-3
    assert "does not meet" in report["verdict"]
