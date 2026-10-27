"""The published section depths must stay in range, and the speed correction stays small on this record."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

RESULT = Path(r"F:\velch_tmp\order_tracking\section_depths.json")


def _payload() -> dict:
    if not RESULT.exists():
        pytest.skip("run scripts/s20_section_depths.py first")
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_every_section_depth_is_a_plausible_corrugation() -> None:
    payload = _payload()
    for name, depth in payload["section_mean_depth_um"].items():
        # Short-pitch corrugation runs 20-100 um peak to peak, i.e. 5-50 um amplitude; allow the
        # document's own 5-400 um window but fail anything outside it loudly.
        assert 5.0 <= float(depth) <= 400.0, (name, depth)


def test_the_speed_correction_is_small_on_this_record() -> None:
    payload = _payload()
    rows = payload["rows"]
    windowed = float(np.median([row["depth_um"] for row in rows]))
    single = float(np.median([row["depth_um_at_single_gain"] for row in rows]))
    # Every section sits at 75.8-77.8 km/h against a 70.8 km/h calibration, so the two medians must
    # agree to a couple of percent.  If this ever grows, the record has started spanning speeds.
    assert windowed == pytest.approx(single, rel=0.05), (windowed, single)


def test_the_design_travels_with_every_depth() -> None:
    payload = _payload()
    assert payload["design"]["crossing_window"] is True
    assert payload["design"]["design_id"] == "A_240"
    for row in payload["rows"]:
        assert row["design"]["design_id"] == "A_240"
        assert row["design"]["wavelength_m"] == pytest.approx(0.0275)
        assert row["gain_source"] in {"interpolated", "extrapolated"}


def test_the_record_spread_is_wider_than_the_section_spread() -> None:
    payload = _payload()
    rows = [row["depth_um"] for row in payload["rows"]]
    sections = list(payload["section_mean_depth_um"].values())
    # Two axle-box columns disagree, so single records must span more than the section means.
    assert max(rows) - min(rows) > max(sections) - min(sections)
