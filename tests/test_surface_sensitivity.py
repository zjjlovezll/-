"""M5 step 1: the forward operator's response to a *known* surface bump.

The report is produced by ``scripts/s112_surface_sensitivity.py --analyze`` from the four archived
0.6 s runs (baseline plus 50/100/200 um blade bumps).  The run archives live in ``scratch/runs``,
which is not versioned, so this test skips -- rather than silently passing -- when the report is not
there; the report itself is committed under ``reports/surface_sensitivity_2026-10-31/``.
"""
from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "surface_sensitivity_2026-10-31" / "sensitivity.json"

pytestmark = pytest.mark.corpus


@pytest.fixture(scope="module")
def report() -> dict:
    if not REPORT.is_file():
        pytest.skip(f"no report at {REPORT}")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_the_response_is_visible_and_on_the_bumped_rail(report: dict) -> None:
    rows = report["rows"]
    assert len(rows) == 3
    assert all(row["visible_fraction"] > 0.10 for row in rows)
    # The left rail carries no bump, so its axle box must not see a comparable response.
    assert all(row["left_over_right"] < 0.5 for row in rows)


def test_the_peak_sits_where_the_bump_was_put(report: dict) -> None:
    centre = float(report["bump"]["centre_m"])
    for row in report["rows"]:
        assert abs(float(row["peak_station_m"]) - centre) < 1.5, row


def test_the_operator_is_only_linear_while_the_stock_carries_the_wheel(report: dict) -> None:
    rows = report["rows"]
    # This is the measured shape of the operator, not an aspiration: the gain stops growing once the
    # stock body starts dropping out under the bump, which already happens at 100 um because the
    # static penetration here is 63.7 um.  If a future change makes the operator linear further out,
    # this assertion should be re-derived rather than relaxed.
    assert report["monotone"] is False
    assert report["linear_regime_amplitudes_um"] == [50.0]
    zero_frames = [row["branch"]["stock"]["zero_frames"] for row in rows]
    assert zero_frames[0] == 0
    assert zero_frames[0] < zero_frames[1] < zero_frames[2]
    assert report["peak_gain_spread"] > 1.5


def test_the_blade_takes_over_as_the_bump_grows(report: dict) -> None:
    blade = [row["branch"]["blade"]["max_kN"] for row in report["rows"]]
    assert blade[0] < blade[1] < blade[2]
    assert blade[-1] > 60.0
