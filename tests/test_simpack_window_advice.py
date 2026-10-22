"""The refusal message must name a window that measures clean, and admit when none does."""

from __future__ import annotations

from pathlib import Path

import pytest

from velch import simpack_case
from velch.simpack_case import CatalogStation


def _stations(mileages: list[float]) -> list[CatalogStation]:
    return [
        CatalogStation(rail="$R", side="right", index=position, station_m=value,
                       path=str(Path("profile.prr")), sha256="0" * 64)
        for position, value in enumerate(mileages, start=1)
    ]


@pytest.fixture()
def piecewise(monkeypatch: pytest.MonkeyPatch) -> None:
    """0.5 mm below 60 m, 12 mm from 60 to 80 m, then 1 mm — a switch, then a running surface."""

    def fake(entries, _profile_template, *, lateral_m=None):  # noqa: ANN001, ANN003
        worst = 0.0
        at = entries[0].station_m
        for entry in entries:
            drop = 0.5 if entry.station_m < 60 else (12.0 if entry.station_m < 80 else 1.0)
            if abs(drop) > abs(worst):
                worst, at = drop, entry.station_m
        return worst, at

    monkeypatch.setattr(simpack_case, "_surface_delta_mm", fake)


def _suggest(mileages: list[float], wanted: float, *, span_hi: float = 140.0, **kwargs: object):
    entries = _stations(mileages)
    return simpack_case.suggest_window(
        entries, {"file": "template.prr"}, travel_s=100.0, ride_s=0.05,
        span_lo=0.0, span_hi=span_hi, wanted_m=wanted, **kwargs)


def test_a_clean_window_is_named_when_one_exists(piecewise: None) -> None:
    found = _suggest([60.0, 70.0, 85.0, 100.0], wanted=60.0)

    assert found is not None
    start, worst = found
    assert start == pytest.approx(85.0), "60 and 70 m sit in the 12 mm band and cannot be offered"
    assert worst <= simpack_case.SURFACE_DROP_WARN_MM


def test_the_nearest_clean_window_wins(piecewise: None) -> None:
    found = _suggest([60.0, 70.0, 85.0, 90.0], wanted=83.0)

    assert found is not None
    assert found[0] == pytest.approx(85.0)


def test_no_candidate_is_admitted_rather_than_invented(piecewise: None) -> None:
    assert _suggest([60.0, 65.0, 70.0, 75.0], wanted=70.0) is None


def test_windows_that_run_past_the_model_are_not_offered(piecewise: None) -> None:
    found = _suggest([85.0, 130.0], wanted=128.0, span_hi=132.0)

    assert found is not None
    assert found[0] != pytest.approx(130.0), "130 m + 5 m of travel runs past 132 m"


def test_the_refusal_message_carries_the_suggestion(piecewise: None) -> None:
    text = simpack_case._advice(  # noqa: SLF001
        _stations([60.0, 70.0, 85.0]), {"file": "template.prr"},
        travel_s=100.0, ride_s=0.05, span_lo=0.0, span_hi=140.0, wanted_m=60.0,
        limit_mm=simpack_case.SURFACE_DROP_WARN_MM)

    assert "85.0 m" in text
    assert "measures within" in text


def test_the_advice_admits_when_nothing_qualifies(piecewise: None) -> None:
    text = simpack_case._advice(  # noqa: SLF001
        _stations([60.0, 65.0, 70.0, 75.0]), {"file": "template.prr"},
        travel_s=100.0, ride_s=0.05, span_lo=0.0, span_hi=140.0, wanted_m=65.0,
        limit_mm=simpack_case.SURFACE_DROP_WARN_MM)

    assert "No window in this model measures within" in text
