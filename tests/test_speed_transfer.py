"""Tests for the speed-transfer probe (round 290).

Three things must hold before the 60/100 km/h rows can be read as evidence about speed rather than about
this file: the scoring must add G-AMP and keep the other three gates separable, a shifted centre must fail
only the location gate, and the selection must refuse a speed that has no archived run instead of silently
returning the 80 km/h one.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s145_speed_transfer as transfer  # noqa: E402


def _fit(amplitude_um: float, centre_m: float) -> dict:
    stations = np.arange(55.0, 61.5, 0.02)
    return {"route": transfer.BUMP_ROUTE, "speed_kmh": 80.0, "run_id": "synthetic",
            "stations": stations, "amplitude_um": amplitude_um, "centre_m": centre_m,
            "share_rms": 0.0, "usable_stations": int(stations.size)}


def test_the_exact_answer_passes_all_four_gates():
    scored = transfer.score(_fit(60.0, 58.5))
    assert scored["gates"] == {"G-ABS": True, "G-REL": True, "G-LOC": True, "G-AMP": True}
    assert scored["p95_um"] == pytest.approx(0.0, abs=1e-9)
    assert scored["worst_bin_relative_pct"] == pytest.approx(0.0, abs=1e-9)
    assert scored["peak_error_m"] == pytest.approx(0.0, abs=1e-9)
    assert all(isinstance(value, bool) for value in scored["gates"].values())


def test_an_over_read_amplitude_fails_only_the_amplitude_gate():
    # 80 um against 60: the profile stays inside 22 um absolute (20 um at the peak) and at the same station,
    # so G-ABS and G-LOC must still pass and only G-AMP may fail.  If the gates were not separable here the
    # 60/100 km/h comparison could not say *which* thing changed with speed.
    scored = transfer.score(_fit(80.0, 58.5))
    assert scored["gates"]["G-AMP"] is False
    assert scored["gates"]["G-LOC"] is True
    assert scored["p95_um"] < transfer.ABSOLUTE_LIMIT_UM
    assert scored["amplitude_relative_pct"] == pytest.approx(33.33, abs=0.05)


def test_a_shifted_centre_fails_the_location_gate():
    scored = transfer.score(_fit(60.0, 58.9))
    assert scored["gates"]["G-LOC"] is False
    assert scored["peak_error_m"] == pytest.approx(0.4, abs=0.02)


def test_the_plan_names_both_speeds_and_both_cases(capsys):
    assert transfer.plan() == 0
    printed = capsys.readouterr().out.splitlines()
    assert len(printed) == 4
    assert sum("--speed-kmh 60" in line for line in printed) == 2
    assert sum("--speed-kmh 100" in line for line in printed) == 2
    assert sum("one_set_bump060.0um.json" in line for line in printed) == 2
    assert sum("straight_one_set.json" in line for line in printed) == 2


def test_selection_refuses_a_speed_that_has_no_archived_run():
    with pytest.raises(SystemExit) as failure:
        transfer.select(transfer.NULL_ROUTE, 130.0)
    assert "130" in str(failure.value)


@pytest.mark.corpus
def test_the_blade_starts_carrying_at_a_fixed_time_not_a_fixed_station():
    """The mechanism: at 60/80/100 km/h the un-bumped blade first carries at the same *time*, 3.4 m apart.

    This is why one station-based calibration cannot transfer: the operating point u0(s) is anchored to the
    run's settling transient, so the same profile is displaced in station by the travel speed.
    """
    rows = {speed: transfer.transition(speed, 0.05) for speed in (60.0, 80.0, 100.0)}
    stations = [row["station_m"] for row in rows.values()]
    times = [row["time_s"] for row in rows.values()]
    assert max(stations) - min(stations) > 1.5          # 56.15 .. 60.19 m measured
    assert max(times) - min(times) <= 0.02              # 0.367 s at all three speeds
    assert stations[0] < stations[1] < stations[2]      # station grows with speed


@pytest.mark.corpus
def test_the_report_records_that_the_inversion_does_not_transfer():
    import json

    report = json.loads(transfer.REPORT.read_text(encoding="utf-8"))
    assert report["self_check_80"]["reproduced"] is True
    assert report["transfers"] is False
    speeds = {row["speed_kmh"]: row for row in report["rows"]}
    assert speeds[80.0]["gates"]["G-ABS"] is True
    for speed in (60.0, 100.0):
        assert speeds[speed]["gates"]["G-ABS"] is False
        assert speeds[speed]["gates"]["G-LOC"] is False
    # the amplitude denominator is the 60 um truth, not the 500 um floor: 66.1 um reads 10.2 %, not 1.2 %
    assert report["rows"][0]["amplitude_relative_pct"] == pytest.approx(10.23, abs=0.05)
    assert report["rows"][0]["amplitude_relative_pct_floor500"] == pytest.approx(1.23, abs=0.05)
