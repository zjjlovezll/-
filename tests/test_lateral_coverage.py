"""The light band is 4 mm wide per pass, so coverage is a pass count -- this pins the arithmetic.

Round 259 measured one pass seeing 4 mm of surface at the 1 % level; round 249 measured one pass's
contact band at 16 mm.  The difference is the band (what the contact touches) and the response
(the lateral distance over which a surface feature still shows up in the load split).

Round 270 asked the complementary question: can passes at different gauge settings actually be laid
side by side to cover the head, and how far does the lever go?  These tests pin the three numbers
that answer it, plus the union arithmetic itself.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

REPORT = (pathlib.Path(__file__).resolve().parents[1] / "reports" / "load_split_inversion_2026-10-31"
          / "lateral_coverage.json")

pytestmark = pytest.mark.corpus


def _report() -> dict:
    if not REPORT.exists():
        pytest.skip(f"{REPORT.name} not built; run scripts/s126_lateral_coverage.py")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_every_gauge_setting_seats_and_the_contact_slides_forwards():
    """A pass that does not seat is not a pass; and opening the gauge must move the contact forward."""
    data = _report()
    offsets = []
    for entry in data["passes"]:
        assert entry["pass_ok"], f"{entry['route']} did not seat (residual {entry['seat_residual_n']:.2e})"
        right = [row for row in entry["contacts"] if row["rail"].endswith("_right") and row.get("active")]
        assert len(right) == 4, entry["route"]
        # all four right-hand contacts of one pass sit at the same lateral position
        assert max(row["offset_from_crown_mm"] for row in right) - min(
            row["offset_from_crown_mm"] for row in right) < 0.05
        offsets.append(right[0]["offset_from_crown_mm"])
    assert offsets == sorted(offsets), offsets
    assert data["passes_ok"] == len(data["passes"]) == 9


def test_the_lever_is_one_point_three_millimetres_of_slide_per_millimetre_of_gauge():
    """16 mm of gauge travelled 20.5 mm of contact -- that ratio is what makes nine passes worth it."""
    data = _report()
    offsets = []
    for entry in data["passes"]:
        right = [row for row in entry["contacts"] if row["rail"].endswith("_right") and row.get("active")]
        offsets.append(right[0]["offset_from_crown_mm"])
    travel = offsets[-1] - offsets[0]
    gauge = data["deltas_mm"][-1] - data["deltas_mm"][0]
    assert travel == pytest.approx(20.5, abs=0.5), travel
    assert travel / gauge == pytest.approx(1.28, abs=0.05)


def test_the_band_covers_about_sixty_percent_of_the_head_and_seventy_of_the_riding_surface():
    """Two head widths, both quoted: the 5 mm-deep head (61.46 mm) and the 1 mm-deep top (37.15 mm)."""
    data = _report()
    bands = [(a, b) for a, b in data["coverage"]["bands_mm"]]
    assert len(bands) == 36  # nine passes x four right-hand contacts

    def coverage(head_mm: float) -> float:
        grid = np.arange(-head_mm / 2.0, head_mm / 2.0, 0.1)
        hit = np.zeros_like(grid, dtype=bool)
        for a, b in bands:
            hit |= (grid >= a) & (grid <= b)
        return float(hit.mean())

    assert coverage(61.46) == pytest.approx(0.584, abs=0.02)
    assert coverage(37.15) == pytest.approx(0.699, abs=0.02)


def test_the_gap_is_outboard_because_no_contact_reaches_past_the_crown():
    """The reason coverage stops at 70 % is geometric: every contact sits inboard of the crown."""
    data = _report()
    top = max(row["offset_from_crown_mm"] for entry in data["passes"]
              for row in entry["contacts"] if row["rail"].endswith("_right") and row.get("active"))
    bottom = min(row["offset_from_crown_mm"] for entry in data["passes"]
                 for row in entry["contacts"] if row["rail"].endswith("_right") and row.get("active"))
    assert top < 2.0, top           # at +8 mm gauge the contact is still on the crown
    assert bottom < -15.0, bottom   # at -8 mm it is deep on the gauge-face side
    # closing that outboard gap would need ~+14 mm more gauge at the measured rate
    assert (18.575 - top) / 1.28 == pytest.approx(14.0, abs=1.5)


SETTLE = (pathlib.Path(__file__).resolve().parents[1] / "reports" / "load_split_inversion_2026-10-31"
          / "seat_after_settle.json")


def test_the_three_settings_that_cannot_start_cost_no_coverage():
    """Seating is necessary but not sufficient: the integrator seats twice, and six of nine survive.

    The three that do not survive are not an edge of the range -- they are {(-6, -4, +2)}, interior
    and non-monotone, because the lateral residual stalls at 104-178 N where the force is flat in y
    (round 247).  What matters for coverage is that losing them loses no band: the union is decided
    by the two extremes.
    """
    if not SETTLE.exists():
        pytest.skip(f"{SETTLE.name} not built; run scripts/s127_seat_after_settle.py")
    settle = json.loads(SETTLE.read_text(encoding="utf-8"))
    rows = {row["delta_mm"]: row for row in settle["rows"]}
    sustainable = sorted(delta for delta, row in rows.items() if row.get("sustainable"))
    assert sustainable == [-8.0, -2.0, 0.0, 4.0, 6.0, 8.0], sustainable
    refused = sorted(set(rows) - set(sustainable))
    assert refused == [-6.0, -4.0, 2.0], refused
    # not a boundary: a boundary would be a prefix or a suffix of the ordered settings
    ordered = sorted(rows)
    assert refused != ordered[: len(refused)] and refused != ordered[-len(refused):]

    data = _report()
    bands = [(a, b) for a, b in data["coverage"]["bands_mm"]]
    deltas = [entry["delta_mm"] for entry in data["passes"]]
    per_delta = {delta: bands[4 * i: 4 * i + 4] for i, delta in enumerate(deltas)}

    def coverage(keys: list[float], head_mm: float = 61.46) -> float:
        grid = np.arange(-head_mm / 2.0, head_mm / 2.0, 0.1)
        hit = np.zeros_like(grid, dtype=bool)
        for key in keys:
            for a, b in per_delta[key]:
                hit |= (grid >= a) & (grid <= b)
        return float(hit.mean())

    assert coverage(sustainable) == pytest.approx(coverage(sorted(per_delta)), abs=1e-9)
