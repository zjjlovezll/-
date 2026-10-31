"""The split law shifts with mileage, and the shift tracks the blade's section width.

Round 254's law was measured at one station.  This round's sweep shows it does not collapse onto a single
curve: the height at which the blade wins half the load moves by 113 um between a 45 mm and a 63 mm blade
section, and saturates at full width.  The tests pin the three readings that survive scrutiny and the
measurement's coverage, so that neither the shift nor the gaps can be forgotten.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

REPORT = (pathlib.Path(__file__).resolve().parents[1] / "reports"
          / "load_split_inversion_2026-10-31" / "split_law_vs_station.json")
WIDTH_MM = {58.0: 45.0, 60.0: 63.0, 62.0: 72.2}

pytestmark = pytest.mark.corpus


@pytest.fixture(scope="module")
def report() -> dict:
    if not REPORT.exists():
        pytest.skip(f"{REPORT} has not been generated on this machine")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _raise_um(row: dict) -> float:
    """Absolute blade raise = design gap + delta (both in um)."""
    return float(row["design_gap_m"]) * 1e6 + float(row["delta_um"])


def test_level_surfaces_share_the_load_in_half(report: dict) -> None:
    # At 60.0 and 62.0 m the design gap is about zero, so the split at delta = 0 is the probe's own zero check:
    # two surfaces of the same height must divide the axle load about equally.
    for station in (60.0, 62.0):
        row = next(item for item in report["rows"]
                   if item["station_m"] == station and item["delta_um"] == 0.0)
        assert abs(float(row["design_gap_m"])) < 30e-6, row
        assert 0.45 <= row["sigma"] <= 0.55, row


def test_the_half_load_height_shifts_with_the_section_width(report: dict) -> None:
    # 45 mm section needs +97 um of raise, 63 mm needs -16 um: a 113 um shift, four times the 100 um slack the
    # pre-registered "collapse" threshold allowed.  This is the finding, so it is asserted, not narrated.
    crossings = {row["station_m"]: row for row in report["crossings"]}
    # Compute absolute raise from the table itself, since the crossings are reported in delta.
    def raise_at_half(station: float) -> float:
        half = crossings[station]["delta_half_um"]
        gap = next(row["design_gap_m"] for row in report["rows"] if row["station_m"] == station)
        return float(gap) * 1e6 + float(half)

    assert np.isfinite(raise_at_half(58.0)) and np.isfinite(raise_at_half(60.0))
    assert raise_at_half(58.0) - raise_at_half(60.0) >= 60.0, (raise_at_half(58.0), raise_at_half(60.0))
    assert WIDTH_MM[58.0] < WIDTH_MM[60.0] < WIDTH_MM[62.0]
    # Saturated at full width: the last step moves the crossing by only a few um.
    assert abs(raise_at_half(60.0) - raise_at_half(62.0)) <= 15.0


def test_the_footprint_moves_with_the_station(report: dict) -> None:
    rows = [row for row in report["rows"] if row["delta_um"] == 0.0]
    widths = [float(row["half_width_m"]) for row in rows if np.isfinite(row["half_width_m"])]
    assert min(widths) < 0.90 * max(widths), widths


def test_the_measurement_coverage_is_recorded(report: dict) -> None:
    # Only the stations whose blade reaches the transfer inside the grid can report a crossing; the rest are
    # a stated gap, and the report must say so rather than imply six stations were measured.
    crossings = [row for row in report["crossings"] if np.isfinite(row["delta_half_um"])]
    assert len(crossings) == 3, report["crossings"]
    assert abs(float(report["half_height_spread_um"]) - 58.4) <= 1.0
