"""The measured split law, and the refutation of round 253's explanation for the amplitude compression.

Round 253 attributed the compression to the two bodies' support compliance.  That is wrong and these tests
say why in a form that cannot drift: the rails share one node, they sink by the same amount, and the gap is a
difference, so the common descent cancels.  What does change inside the transition is the footprint.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SINK = ROOT / "reports" / "load_split_inversion_2026-10-31" / "support_sink.json"
LAW = ROOT / "reports" / "load_split_inversion_2026-10-31" / "split_law.json"

pytestmark = pytest.mark.corpus


@pytest.fixture(scope="module")
def sink() -> dict:
    if not SINK.exists():
        pytest.skip(f"{SINK} has not been generated on this machine")
    return json.loads(SINK.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def law() -> dict:
    if not LAW.exists():
        pytest.skip(f"{LAW} has not been generated on this machine")
    return json.loads(LAW.read_text(encoding="utf-8"))


def test_every_rail_sinks_by_the_same_amount(sink: dict) -> None:
    # Two bodies can only sink differently if they sit on different nodes.  They do not: the span is zero.
    sinks = [row["sink_m"] for row in sink["rows"]]
    assert len(sinks) == 8, sinks
    assert max(sinks) - min(sinks) == pytest.approx(0.0, abs=1e-12)
    assert sink["sink_span_m"] == pytest.approx(0.0, abs=1e-12)


def test_the_sink_follows_the_case_support_stiffness(sink: dict) -> None:
    # 1.2027 mm at 60.15 kN is exactly F/k_z; a different ratio would mean something else is carrying the rail.
    for row in sink["rows"]:
        assert abs(abs(row["sink_m"]) - row["force_n"] / sink["k_z_n_m"]) <= 1e-6, row


def test_the_split_law_is_monotone_in_blade_height(law: dict) -> None:
    rows = sorted(law["rows"], key=lambda row: row["offset_um"])
    sigma = [row["sigma"] for row in rows]
    # Raising the blade (decreasing offset) can only increase its share, so sigma must fall as offset rises.
    assert sigma == sorted(sigma, reverse=True), sigma
    assert sigma[0] == pytest.approx(1.0, abs=1e-9)      # blade fully raised -> carries everything
    assert sigma[-1] == pytest.approx(0.0, abs=1e-9)     # blade fully lowered -> carries nothing


def test_the_transition_is_narrow_and_the_footprint_changes_across_it(law: dict) -> None:
    rows = {row["offset_um"]: row for row in law["rows"]}
    # sigma crosses one half inside the measured grid, between -150 and -40 um of blade height.
    assert any(-150.0 <= value <= -40.0 for value in law["crossings_um"]), law["crossings_um"]
    # The footprint is the mechanism: it shrinks when the narrower blade takes over.
    widths = [row["half_width_m"] for row in law["rows"]]
    assert min(widths) < 0.85 * max(widths), widths
    assert rows[-250.0]["half_width_m"] < rows[0.0]["half_width_m"]
