"""Does the round-261 inversion still work when the pass sits 4.6 mm further out on the head?

Round 270 measured that the gauge moves the contact 1.28 mm per millimetre and that a pass at
delta = +4 mm contacts 3.3 mm inboard of the crown, against 7.9 mm at nominal gauge.  Round 261's
two-parameter fit was calibrated on nominal-gauge passes only, so "assemble the light band from
several passes" needs this answer first: same amplitude, same fit, a pass somewhere else on the head.

These tests pin the construction (only the right rail moves, only the blade carries the bump) and the
report, if it has been built.  They do not re-run anything.
"""
from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VARIANT = ROOT.parent / "scratch" / "s128" / "one_set_gauge+4mm_bump060.0um.json"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "band_assembly.json"
DELTA_M = 4.0e-3
AMPLITUDE_M = 60.0e-6


@pytest.fixture(scope="module")
def variant() -> dict:
    if not VARIANT.exists():
        pytest.skip(f"{VARIANT.name} not built; run scripts/s128_band_assembly.py --build")
    return json.loads(VARIANT.read_text(encoding="utf-8"))


@pytest.mark.corpus
def test_only_the_right_rail_moves_and_only_the_blade_carries_the_bump(variant):
    """A gauge change moves one rail; the bump belongs to one body.  Both are checked, not assumed."""
    left, right = variant["rail_templates"]
    assert left["stations"][0]["profile"]["y_offset_m"] == pytest.approx(-0.7526099, abs=1e-9)

    stock = [body for body in right["bodies"] if body["id"] == "stock"][0]
    blade = [body for body in right["bodies"] if body["id"] == "blade"][0]
    frog = [body for body in right["bodies"] if body["id"] == "frog"][0]

    for body in (stock, frog):
        assert all(float(st["profile"].get("z_offset_m", 0.0)) == 0.0 for st in body["stations"])
    heights = [float(st["profile"]["z_offset_m"]) for st in blade["stations"]]
    assert max(heights) == pytest.approx(AMPLITUDE_M, rel=1e-3)
    assert min(heights) < 1e-9                      # the gaussian dies away at the ends
    assert sum(1 for h in heights if h > 0.5 * AMPLITUDE_M) < len(heights) / 4


@pytest.mark.corpus
def test_the_gauge_shift_is_the_declared_four_millimetres(variant):
    """The two rails' first stations differ by 1.4930 + 4 mm -- the same arithmetic round 270 used."""
    left, right = variant["rail_templates"]
    gauge = (right["stations"][0]["profile"]["y_offset_m"]
             - left["stations"][0]["profile"]["y_offset_m"])
    # the crown offset baked into the build is 1.5092 m at nominal gauge (round 249/270), so the
    # variant must be exactly DELTA_M wider than the canonical case, which this reads from disk
    canonical = json.loads((ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases"
                            / "straight_one_set.json").read_text(encoding="utf-8"))
    base_gauge = (canonical["rail_templates"][1]["stations"][0]["profile"]["y_offset_m"]
                  - canonical["rail_templates"][0]["stations"][0]["profile"]["y_offset_m"])
    assert gauge - base_gauge == pytest.approx(DELTA_M, abs=1e-9)


@pytest.mark.corpus
def test_the_moved_pass_is_judged_with_the_same_gates_as_the_nominal_one():
    """The gates are the round-261 ones; this pins that they were not edited for the moved pass."""
    if not REPORT.exists():
        pytest.skip("report not built; run scripts/s128_band_assembly.py --report")
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    assert payload["delta_mm"] == pytest.approx(4.0)
    assert payload["amplitude_um"] == pytest.approx(60.0)
    labels = {row["label"] for row in payload["rows"]}
    assert labels == {"moved pass", "control at nominal gauge"}, labels
    for row in payload["rows"]:
        assert set(row["gates"]) == {"G-ABS", "G-REL", "G-LOC"}
        assert 0.0 <= row["p95_um"]
    moved = [row for row in payload["rows"] if row["delta_mm"] == 4.0][0]
    control = [row for row in payload["rows"] if row["delta_mm"] == 0.0][0]
    assert moved["truth_um"] == control["truth_um"] == pytest.approx(60.0)
