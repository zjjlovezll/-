"""The seating table has the right zeros and the wrong derivative.

Round 284 showed the seated split equals the rolling split at ten stations (median 0.0022).  That is the zero
point.  This round asks the derivative: same station, same single-station raise, compare the slope the seating
probe gives with the slope a rolling run produces.

  station   seated slope   rolling slope   ratio
  58.00        +3775.2 /m      +1800.4 /m    0.48
  58.50        +4095.0 /m      +3906.5 /m    0.95

So a seating-only table overstates the response by a factor that is *not* constant (0.48 vs 0.95), which means
it cannot be repaired by one scale factor -- and it cannot serve as the forward for amplitude inversion.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "rolling_slope.json"


@pytest.fixture(scope="module")
def report() -> dict:
    if not REPORT.exists():
        pytest.skip("the rolling-slope campaign has not been produced yet")
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.mark.corpus
def test_both_archived_stations_rise_with_the_raise(report: dict) -> None:
    rows = report["rows"]
    assert len(rows) == 4
    by_station = {}
    for row in rows:
        by_station.setdefault(row["station_m"], []).append(row)
    for station, group in by_station.items():
        null = group[0]["share_rolling_null"]
        for row in group:
            assert row["share_rolling"] > null, (station, row["raise_um"])
            assert row["share_rolling"] <= 1.0 + 1e-12


@pytest.mark.corpus
def test_the_zeros_agree_but_the_slopes_do_not(report: dict) -> None:
    ratios = {item["station_m"]: item["ratio"] for item in report["comparisons"]}
    assert ratios[58.0] == pytest.approx(0.48, abs=0.05)
    assert ratios[58.5] == pytest.approx(0.95, abs=0.05)
    # the ratio is not a constant: 58.0 m responds at half the seated rate, 58.5 m at almost the same rate
    assert abs(ratios[58.5] - ratios[58.0]) > 0.3
    assert report["r4"] is False
    assert report["r5"] is True


@pytest.mark.corpus
def test_the_seated_and_rolling_slopes_are_the_stored_numbers(report: dict) -> None:
    comparisons = {item["station_m"]: item for item in report["comparisons"]}
    assert comparisons[58.0]["seated_slope_per_m"] == pytest.approx(3775.2, rel=0.01)
    assert comparisons[58.0]["rolling_slope_per_m"] == pytest.approx(1800.4, rel=0.01)
    assert comparisons[58.5]["seated_slope_per_m"] == pytest.approx(4095.0, rel=0.01)
    assert comparisons[58.5]["rolling_slope_per_m"] == pytest.approx(3906.5, rel=0.01)


@pytest.mark.corpus
def test_the_verdict_says_the_derivative_is_wrong(report: dict) -> None:
    verdict = report["verdict"]
    assert "wrong derivative" in verdict
    assert "right zeros" in verdict
    for banned in ("recovered", "amplitude", "slope matches"):
        assert banned not in verdict


def test_the_station_table_stops_where_the_blade_profile_stops() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import s142_rolling_slope as slope  # noqa: E402

    # 61 and 62 m alias onto the blade's last station (60.962 m), so they must not be probed as if distinct
    assert max(slope.STATIONS) <= 60.0
    assert len(set(slope.STATIONS)) == len(slope.STATIONS)
