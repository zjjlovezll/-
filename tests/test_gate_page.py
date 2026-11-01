"""Pins the per-speed gate page (scripts/s156_gate_page.py).

Four pre-registered synthetic gates per speed, plus the physical location column measured on the null
geometry and the shift the injected lowering itself produces.  Frozen here:

* the gate values, so a change in the fit cannot silently turn a FAIL into a PASS;
* the null-route engage at 1 % and 5 % share, and that the threshold span explains only ~0.03 m -- this is
  what refutes "the 0.42 m late engage is a 1 kN detection artefact";
* the bump shift (-0.23 / -0.19 m), the injected 60 um lowering moving the engagement earlier by itself;
* that 60 km/h is reported as pending rather than dropped;
* that the engage sits inside [first touch 57.733, crowns level 58.423], which is why comparing a 5 % share
  station against the first-touch reference is not yet a verdict.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import s156_gate_page as page  # noqa: E402

FIRST_TOUCH_M = 57.733
CROWNS_LEVEL_M = 58.423


@pytest.fixture(scope="module")
def table() -> dict:
    return page.measure()


@pytest.mark.corpus
def test_the_synthetic_gates_reproduce(table: dict) -> None:
    slow = table["80"]["gates"]
    assert slow["values"]["G-ABS"] == pytest.approx(6.25, abs=0.05)
    assert slow["values"]["G-REL"] == pytest.approx(1.25, abs=0.02)
    assert slow["values"]["G-LOC"] == pytest.approx(0.014, abs=0.005)
    assert slow["values"]["G-AMP"] == pytest.approx(10.37, abs=0.05)
    assert slow["all_passed"] is False          # the amplitude gate is the one that fails at 80 km/h
    assert slow["passed"]["G-AMP"] is False and slow["passed"]["G-ABS"] is True

    fast = table["100"]["gates"]
    assert fast["values"]["G-LOC"] == pytest.approx(0.419, abs=0.005)
    assert fast["values"]["G-REL"] == pytest.approx(2.34, abs=0.02)
    assert fast["all_passed"] is False


@pytest.mark.corpus
def test_the_threshold_does_not_explain_the_late_engage(table: dict) -> None:
    for key in ("80", "100"):
        scan = table[key]["engage"]["by_threshold"]
        assert scan["0.01"] == pytest.approx(58.12, abs=0.02)
        assert scan["0.05"] == pytest.approx(58.15, abs=0.02)
        # the whole 1 %->10 % span moves the station by a few centimetres, not by 0.4 m
        assert scan["0.10"] - scan["0.01"] < 0.10


@pytest.mark.corpus
def test_the_bump_moves_the_engagement_earlier_by_itself(table: dict) -> None:
    for key, expected in (("80", -0.233), ("100", -0.194)):
        shift = table[key]["bump_shift_m"]
        assert shift["0.05"] == pytest.approx(expected, abs=0.02)
        spread = max(shift.values()) - min(shift.values())
        assert spread < 0.05, f"bump shift varies across thresholds by {spread:.3f} m"


@pytest.mark.corpus
def test_60_kmh_is_pending_not_dropped(table: dict) -> None:
    assert table["60"]["status"] == "pending"
    assert page.verdict(table)["pending"] == ["60"]


@pytest.mark.corpus
def test_the_engage_lies_between_first_touch_and_crowns_level(table: dict) -> None:
    for key in ("80", "100"):
        station = table[key]["engage"]["by_threshold"]["0.05"]
        assert FIRST_TOUCH_M < station < CROWNS_LEVEL_M, f"{key} engage {station:.3f} m outside the interval"
