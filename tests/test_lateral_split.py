"""Pin the imposed-displacement split: the direction is right and the size is seventeen times short.

Round 308 read the archives and found a 3.096 mm lateral difference at 58.150 m between the 60 and 80 km/h
runs, but its pre-registered sign predicate had the direction backwards, so the mechanism stayed open.  Round
309 imposed the displacement instead of inferring it, which needs no convention, and registered two claims:

* ``H9`` -- the contact's absolute y moves *against* the imposed q[y] with a magnitude in [0.5, 1.5];
* ``H10`` -- at dy = -3.096 mm the blade's share at 58.150 m lands in [3 %, 8 %].

Both came out true, and the second is nearly vacuous: at the 5 % crossing station the share is about 5 % before
anything is displaced, so the window cannot discriminate.  The informative number is therefore not the flag but
the conversion: the displacement buys 1.03 percentage points of share, the share rises 120 pp per metre of
station, so the displacement is worth **8.6 mm** of station against the **145 mm** that has to be explained.
It explains the direction and 6 % of the size.

That is pinned here so the next round cannot quote ``H10`` as evidence that the lateral registration carries the
offset, and so the ratio cannot drift: the shortfall is the point.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import s161_lateral_split as probe  # noqa: E402

REPORTS = ROOT / "reports" / "load_split_inversion_2026-10-31"
LATERAL = REPORTS / "lateral_split.json"
GAP = REPORTS / "effective_gap.json"
REQUIRED_OFFSET_M = 0.145


@pytest.fixture(scope="module")
def sweep() -> dict:
    assert LATERAL.is_file(), f"missing {LATERAL}"
    return json.loads(LATERAL.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gap() -> dict:
    assert GAP.is_file(), f"missing {GAP}"
    return json.loads(GAP.read_text(encoding="utf-8"))


def _row(sweep: dict, displacement_mm: float) -> dict:
    match = [row for row in sweep["rows"] if abs(1e3 * row["displacement_m"] - displacement_mm) < 1e-9]
    assert match, f"no row at {displacement_mm} mm"
    return match[0]


def test_the_displacement_flips_the_share_the_way_the_archive_needs(sweep: dict) -> None:
    assert len(sweep["rows"]) == 6
    assert 1e3 * _row(sweep, -3.096)["displacement_m"] == pytest.approx(-3.096, abs=1e-9)
    negative = _row(sweep, -3.096)["share"]
    centred = _row(sweep, 0.0)["share"]
    positive = _row(sweep, 3.0)["share"]
    assert negative == pytest.approx(0.0525, abs=5e-4)
    assert centred == pytest.approx(0.0422, abs=5e-4)
    assert positive == pytest.approx(0.0, abs=1e-9)
    # Negative q[y] raises the blade's share, which is the direction the 60 km/h archive recorded.
    assert negative > centred > positive


def test_the_contact_moves_against_the_imposed_coordinate(sweep: dict) -> None:
    slope = sweep["slopes"]["lever_y_per_displacement"]
    assert slope == pytest.approx(-0.5222, abs=2e-3)
    low, high = sweep["constants"]["lever_slope_window"]
    assert -high <= slope <= -low
    assert sweep["H9_convention_confirmed"] is True
    # ... and the contacts do move with the wheelset, not a pinned rail feature.
    moved = _row(sweep, -3.096)["stock_y_m"] - _row(sweep, 3.0)["stock_y_m"]
    assert moved > 1.0e-3


def test_the_registered_window_was_nearly_vacuous(sweep: dict) -> None:
    """At the 5 % crossing station almost any state leaves the share near 5 %, so H10 cannot discriminate."""
    centred = _row(sweep, 0.0)["share"]
    assert sweep["H10_mechanism_confirmed"] is True
    assert abs(centred - 0.05) < 0.01, "the undisplaced state is already within a point of the target"
    low, high = sweep["constants"]["share_window"]
    assert low <= _row(sweep, -3.096)["share"] <= high


def test_the_displacement_is_worth_eight_millimetres_against_one_hundred_and_forty_five(
    sweep: dict, gap: dict
) -> None:
    rows = {round(row["station_m"], 3): row["share_measured"] for row in gap["stations"]}
    rate = 100.0 * (rows[58.175] - rows[58.125]) / (58.175 - 58.125)
    assert rate == pytest.approx(120.0, abs=1.0), "percentage points of share per metre of station"

    gain = 100.0 * (_row(sweep, -3.096)["share"] - _row(sweep, 0.0)["share"])
    assert gain == pytest.approx(1.03, abs=0.02)
    equivalent = gain / rate
    assert equivalent == pytest.approx(0.0086, abs=2e-4)
    assert REQUIRED_OFFSET_M / equivalent > 15.0, "the registration is at least fifteen times too small"
    assert equivalent < 0.02, "8.6 mm of station, not 145 mm"


def test_two_routes_agree_at_the_undisplaced_state(sweep: dict, gap: dict) -> None:
    rows = {round(row["station_m"], 3): row["share_measured"] for row in gap["stations"]}
    low, high = rows[58.125], rows[58.175]
    interpolated = low + (high - low) * (58.150 - 58.125) / (58.175 - 58.125)
    assert interpolated == pytest.approx(0.0448, abs=1e-3)
    assert _row(sweep, 0.0)["share"] == pytest.approx(interpolated, abs=0.01)
    assert probe.STATION_M == pytest.approx(58.150)
