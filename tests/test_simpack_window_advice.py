"""The suggestion must name a window whose *whole vehicle footprint* measures clean.

The rear axle sits 10 m behind ``x_start``, so a candidate start is only clean if the stations behind
it are clean too — an earlier version looked 2 m back and would happily offer a window whose rear axle
rode the switch blade.  The measurement is faked here: what is under test is the search, not the
profile reader.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from velch import simpack_case
from velch.simpack_case import CatalogStation

REACH = 10.0


def _stations(mileages: list[float]) -> list[CatalogStation]:
    return [
        CatalogStation(rail="$R", side="right", index=position, station_m=value,
                       path=str(Path("profile.prr")), sha256="0" * 64)
        for position, value in enumerate(mileages, start=1)
    ]


@pytest.fixture()
def step(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clean below 40 m and above 60 m; a 12 mm step in between — a switch, then a running surface."""

    def fake(entries, _profile_template):  # noqa: ANN001
        worst = 0.0
        at = entries[0].station_m
        for entry in entries:
            crown = 12.0 if 40.0 <= entry.station_m <= 60.0 else 0.0
            if abs(crown) > abs(worst):
                worst, at = crown, entry.station_m
        return worst, at, 0.0

    monkeypatch.setattr(simpack_case, "_crown_delta_mm", fake)


def _suggest(mileages: list[float], wanted: float, *, span_hi: float = 200.0, **kwargs: object):
    return simpack_case.suggest_window(
        _stations(mileages), {"file": "template.prr"}, travel_s=100.0, ride_s=0.05,
        span_lo=0.0, span_hi=span_hi, wanted_m=wanted, reach_m=REACH, **kwargs)


def test_a_window_whose_rear_axle_rides_the_step_is_not_offered(step: None) -> None:
    """65 m looks clean forward, but its rear axle sits at 55 m — inside the step."""

    found = _suggest([55.0, 65.0, 80.0], wanted=65.0)

    assert found is not None
    assert found[0] == pytest.approx(80.0), "80 m is the nearest start whose footprint is clean"


def test_a_clean_window_is_named_when_one_exists(step: None) -> None:
    found = _suggest([20.0, 30.0, 70.0], wanted=25.0)

    assert found is not None
    start, worst = found
    assert start == pytest.approx(20.0)
    assert worst == pytest.approx(0.0, abs=1e-9)


def test_the_nearest_clean_window_wins(step: None) -> None:
    found = _suggest([10.0, 20.0, 30.0], wanted=26.0)

    assert found is not None
    assert found[0] == pytest.approx(30.0)


def test_no_candidate_is_admitted_rather_than_invented(step: None) -> None:
    """Every candidate's footprint touches the step, so nothing is offered."""

    assert _suggest([45.0, 50.0, 55.0], wanted=50.0) is None


def test_windows_that_run_past_the_model_are_not_offered(step: None) -> None:
    """100 m/s x 0.05 s = 5 m of travel, so a start at 197 m would need coverage to 202 m."""

    assert _suggest([196.0, 197.0], wanted=196.0, span_hi=200.0) is None


def test_the_advice_names_the_window_it_found(step: None) -> None:
    text = simpack_case._advice(  # noqa: SLF001
        _stations([20.0, 30.0, 70.0]), {"file": "template.prr"},
        travel_s=100.0, ride_s=0.05, span_lo=0.0, span_hi=200.0, wanted_m=25.0,
        limit_mm=simpack_case.CROWN_WARN_MM, reach_m=REACH)

    assert "20.0 m" in text
    assert "worst" in text


def test_the_advice_admits_when_nothing_qualifies(step: None) -> None:
    text = simpack_case._advice(  # noqa: SLF001
        _stations([45.0, 50.0, 55.0]), {"file": "template.prr"},
        travel_s=100.0, ride_s=0.05, span_lo=0.0, span_hi=200.0, wanted_m=50.0,
        limit_mm=simpack_case.CROWN_WARN_MM, reach_m=REACH)

    assert "No window in this model has crown heights within" in text
