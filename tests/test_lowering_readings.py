"""M3: the five readings of "the blade reaches the running surface", pinned by arithmetic.

The same event has been quoted as 57.733 / 58.423 / 57.019 / 64.900 / 68.160 m.  Two of those are
interpolations of a *table* rather than of the drawn sections, and both land late:

  * the width table (3/30/72 mm anchors) is a straight line through a convex curve, so it keeps the
    blade "below the stock" for another 2.6 m;
  * the retired builder's mileage-keyed z-offset table has its last two anchors on the flat part
    (60.047 m at +0.178 mm, 70.848 m at -0.090 mm) and was read linearly, which puts the crossing at
    64.58 m -- that is the 64.900 m that was quoted, and it is 6.7 m late.

These tests recompute the numbers from the case and the sections, so a future edit that changes the
blade geometry has to face them.

    PYTHONPATH=src python -m pytest tests/test_lowering_readings.py -q
"""
from __future__ import annotations

import json
import sys
import pathlib

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s110_lowering_readings as readings  # noqa: E402

pytestmark = pytest.mark.corpus

STATIC_PENETRATION_M = 65.4661e-6


@pytest.fixture(scope="module")
def measured():
    """Sample the blade and stock crowns at every declared blade station."""

    from velch.vehicle import load_vehicle_case

    case = load_vehicle_case(readings.CASE)
    rail = next(item for item in case.rails if item.id == readings.RAIL)
    bodies = {body.id: body for body in rail.contact_bodies}
    blade, stock = bodies["blade"], bodies["stock"]

    raw = json.loads(readings.CASE.read_text(encoding="utf-8"))
    widths: dict[float, float] = {}
    for template in raw["rail_templates"]:
        if str(template.get("id", "")) != str(rail.template_id):
            continue
        for body in template.get("bodies", ()):
            if str(body.get("id")) != "blade":
                continue
            for station in body["stations"]:
                value = readings.width_mm_of(str(station["profile"]["file"]))
                if np.isfinite(value):
                    widths[round(float(station["s_m"]), 6)] = value
    stations = np.array(sorted(widths))
    lowering = np.array([readings.crown_m(stock.series, float(s)) - readings.crown_m(blade.series, float(s))
                         for s in stations])
    return {"case": case, "stations": stations, "widths": np.array([widths[s] for s in stations]),
            "lowering": lowering}


def test_the_drawn_sections_put_the_first_touch_near_fifty_eight(measured):
    """At the declared stations the blade comes within one static penetration at 57.844 m."""

    touch = readings.first_crossing(measured["stations"], measured["lowering"], STATIC_PENETRATION_M)
    level = readings.first_crossing(measured["stations"], measured["lowering"], 0.0)
    assert touch == pytest.approx(57.844, abs=0.02)
    assert level == pytest.approx(58.476, abs=0.02)
    assert 0.0 < level - touch < 1.0


def test_the_three_anchor_width_table_is_late_by_about_two_and_a_half_metres(measured):
    three = readings.three_anchor_lowering_mm(measured["widths"]) * 1e-3
    touch_three = readings.first_crossing(measured["stations"], three, STATIC_PENETRATION_M)
    touch = readings.first_crossing(measured["stations"], measured["lowering"], STATIC_PENETRATION_M)
    assert touch_three == pytest.approx(60.452, abs=0.15)
    assert touch_three - touch > 2.0


def test_the_retired_mileage_table_reproduces_the_quoted_sixty_four_point_nine(measured):
    table_s = np.array([anchor[0] for anchor in readings.RETIRED_OFFSET_TABLE])
    table_d = np.array([anchor[1] for anchor in readings.RETIRED_OFFSET_TABLE]) * 1e-3
    grid = np.arange(table_s[0], table_s[-1], readings.STEP_M)
    crossing = readings.first_crossing(grid, np.interp(grid, table_s, table_d), STATIC_PENETRATION_M)
    assert crossing == pytest.approx(64.584, abs=0.2)
    assert abs(crossing - readings.QUOTED["retired_interpolated_m"]) < 0.5


def test_the_tip_lowering_is_fifteen_millimetres_and_the_touch_is_a_hundredth_of_it(measured):
    assert measured["lowering"][0] == pytest.approx(15.007e-3, abs=0.05e-3)
    assert measured["widths"][0] == pytest.approx(3.0)
    touch = readings.first_crossing(measured["stations"], measured["lowering"], STATIC_PENETRATION_M)
    index = int(np.argmin(np.abs(measured["stations"] - touch)))
    assert measured["lowering"][index] == pytest.approx(STATIC_PENETRATION_M, abs=0.02e-3)
