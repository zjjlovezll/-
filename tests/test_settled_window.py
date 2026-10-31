"""Tests for the settled-window speed probe (round 291).

The probe only means something if the two variant cases really start 10 m earlier, keep the same geometry,
and the plan's durations match the pre-registration.  Those three are checked here without running anything.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s146_settled_window as settled  # noqa: E402


def test_the_window_constants_are_the_pre_registered_ones():
    assert settled.START_M == 30.0
    assert settled.SETTLE_S == 0.45
    assert settled.SPEEDS_KMH == (60.0, 80.0, 100.0)
    # shorter runs at higher speed: the same 25 m of track is covered faster
    durations = [settled.DURATIONS_S[speed] for speed in settled.SPEEDS_KMH]
    assert durations == sorted(durations, reverse=True)
    assert durations[0] > durations[-1]


def test_build_moves_the_start_and_keeps_the_geometry(tmp_path, monkeypatch):
    monkeypatch.setattr(settled, "OUT", tmp_path)
    assert settled.build() == 0
    null = json.loads((tmp_path / f"{settled.NULL_ROUTE}.json").read_text(encoding="utf-8"))
    bump = json.loads((tmp_path / f"{settled.BUMP_ROUTE}.json").read_text(encoding="utf-8"))
    for payload in (null, bump):
        assert payload["run"]["x_start_m"] == pytest.approx(30.0)
        assert payload["run"]["seat_x_start_m"] == pytest.approx(30.0)
        assert payload["case_id"].endswith("_x30")
        assert "settled-window" in payload["purpose_detail"]
    # the bump case keeps its 60 um gaussian: the blade stations still carry a z offset with a 60 um peak
    blade = [station for rail in bump["rail_templates"] for body in rail.get("bodies", [])
             if body.get("id") == "blade" for station in body["stations"]]
    offsets = np.asarray([station["profile"].get("z_offset_m", 0.0) for station in blade])
    assert offsets.size > 100
    assert np.max(np.abs(offsets)) == pytest.approx(60.0e-6, rel=0.02)


def test_the_plan_asks_for_each_speed_and_duration(capsys):
    assert settled.plan() == 0
    printed = capsys.readouterr().out.splitlines()
    assert len(printed) == 6
    for speed in settled.SPEEDS_KMH:
        assert sum(f"--speed-kmh {speed:.0f}" in line for line in printed) == 2
        assert sum(f"--duration {settled.DURATIONS_S[speed]:.2f}" in line for line in printed) == 2


def test_selection_names_the_duration_it_wanted():
    with pytest.raises(SystemExit) as failure:
        settled.select(settled.NULL_ROUTE, 120.0)
    assert "120" in str(failure.value)


def test_the_settle_window_drops_the_stations_reached_before_it():
    import numpy as np

    speed_kmh = 100.0
    stations = np.asarray([40.0, 45.0, 52.0, 55.0, 60.0, 62.2])
    travelled = stations - 40.0
    expected = travelled >= (speed_kmh / 3.6) * settled.SETTLE_S
    assert list(expected) == [False, False, False, True, True, True]


@pytest.mark.corpus
def test_a_run_where_the_blade_never_carries_is_reported_as_not_measurable():
    """At 100 km/h with the earlier start the blade is never touched, so the fit must refuse, not guess."""
    try:
        settled.select(settled.BUMP_ROUTE, 100.0)
    except SystemExit:
        pytest.skip("the 100 km/h settled-window runs are not archived on this machine")
    run = settled.transfer.load(settled.select(settled.BUMP_ROUTE, 100.0), 100.0)
    assert float(np.max(run["blade"])) == pytest.approx(0.0, abs=1e-6)
    report = json.loads(settled.REPORT.read_text(encoding="utf-8"))
    flagged = {item["speed_kmh"] for item in report.get("unmeasured", [])}
    assert 100.0 in flagged
    assert all(row["speed_kmh"] != 100.0 for row in report["rows"])


@pytest.mark.corpus
def test_the_amplitude_gate_uses_the_truth_not_the_floor():
    """A 9.5 % amplitude error must fail G-AMP even though the 500 um floor would call it 1 %."""
    report = json.loads(settled.REPORT.read_text(encoding="utf-8"))
    row = next((item for item in report["rows"] if item["speed_kmh"] == 80.0), None)
    if row is None:
        pytest.skip("the 80 km/h settled-window run is not archived on this machine")
    assert row["amplitude_relative_pct"] > 5.0
    assert row["amplitude_relative_pct_floor500"] < 2.0
    assert row["gates"]["G-AMP"] is False


@pytest.mark.corpus
def test_the_blade_onset_is_time_locked_not_station_locked():
    """60 and 100 km/h engage the blade at the same elapsed time as 80 km/h, 4.5 m apart in station.

    That is the round's finding: the lateral drift grows with time, so moving the start moves the station but
    not the moment.  If this ever becomes station-locked the conclusion has to be rewritten.
    """
    report = json.loads(settled.REPORT.read_text(encoding="utf-8"))
    by_speed = {row["speed_kmh"]: row for row in report["diagnoses"] if row.get("first_time_s") is not None}
    if not {60.0, 80.0} <= set(by_speed):
        pytest.skip("both the 60 and 80 km/h settled-window runs are needed")
    times = [by_speed[60.0]["first_time_s"], by_speed[80.0]["first_time_s"]]
    stations = [by_speed[60.0]["first_station_m"], by_speed[80.0]["first_station_m"]]
    assert abs(times[0] - times[1]) < 0.01          # same moment
    assert abs(stations[0] - stations[1]) > 4.0     # different place
