"""Tests for the matched-window cross-speed comparison (round 299).

The comparison itself is a table of four numbers per speed, so what is worth pinning is the machinery:
the window, the declared model, the speed guard (B052 must never come back through the back door), and
the one row that already exists end to end (80 km/h).
"""

from __future__ import annotations

import math
import pathlib
import sys

import pytest

pytestmark = pytest.mark.corpus

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import s152_cross_speed as cross  # noqa: E402


def test_the_window_and_the_declared_model_are_the_preregistered_ones():
    assert (cross.WINDOW_LO_M, cross.WINDOW_HI_M) == (56.0, 65.0)
    assert cross.TRUTH_AMPLITUDE_UM == 60.0
    assert cross.CENTRE_M == 58.5
    assert cross.WIDTH_M == 1.20
    assert cross.SPEEDS_KMH == (60.0, 80.0, 100.0)
    # every duration must carry the wheel across the whole window; the two runs made for this
    # comparison travel exactly the nine metres, the reused 80 km/h pair travels further (fine)
    for speed, (_null, _bump, duration) in cross.RUNS.items():
        travelled = (speed / 3.6) * duration
        assert travelled >= 9.0, (speed, duration, travelled)
        if speed in (60.0, 100.0):
            assert 8.8 <= travelled <= 9.4, (speed, duration, travelled)


def test_the_speed_guard_refuses_a_row_that_does_not_exist():
    with pytest.raises(SystemExit):
        cross.select("one_set_x30", 100.0, 0.99)


def test_the_guard_accepts_the_existing_eighty_and_reports_a_matching_speed():
    row = cross.select("one_set_x30", 80.0, 1.00)
    assert row["run_id"].startswith("one_set_x30-080.00kmh")


def test_the_loader_uses_the_runs_own_speed_for_the_station_column():
    run = cross.load("one_set_x30", 80.0, 1.00)
    span = float(run["station"][-1] - run["station"][0])
    expected = (80.0 / 3.6) * float(run["times"][-1] - run["times"][0])
    assert math.isclose(span, expected, rel_tol=1e-9)


def test_the_eighty_row_reproduces_the_numbers_the_earlier_rounds_quoted():
    state = cross.null_state(80.0)
    row = cross.fit(80.0, state)
    assert math.isclose(state["engage_station_m"], 58.156, abs_tol=0.02)
    assert math.isclose(row["amplitude_um"], 66.2, abs_tol=0.4)
    assert math.isclose(row["centre_m"], 58.514, abs_tol=0.01)
    assert math.isclose(row["p95_um"], 6.25, abs_tol=0.3)
    assert row["G-ABS"] and row["G-REL"] and row["G-LOC"]
    assert not row["G-AMP"], "the amplitude gate is the one that fails at 80 km/h -- keep it visible"


def test_the_verdict_is_derived_from_the_rows_and_not_asserted():
    payload = cross.report((80.0,))
    assert payload["passing_speeds"] == [] or payload["passing_speeds"] == [80.0]
    assert payload["carries_across_speed"] == all(row["gates"] for row in payload["rows"])
    for row in payload["rows"]:
        assert row["gates"] == all(row[key] for key in ("G-ABS", "G-REL", "G-LOC", "G-AMP"))
