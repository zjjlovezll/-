"""Pin what the engage-station measurement says about the lateral registration -- and what it refused.

Round 307 established that the two-spring split is speed-independent (58.145 m at every speed) while the
measured engage(5 %) station is not (58.000 at 60 km/h, 58.156 and 58.153 at 80 and 100).  Round 308 read the
archived runs to find a carrier for that difference and pre-registered H8: the front wheelset at 58.150 m
must be displaced by at least 0.20 mm towards the blade at 60 km/h.

The measurement refused that predicate, and the refusal is pinned here rather than quietly re-worded:

* the displacement is large and real -- 3.096 mm, fifteen times the threshold, with a drift of -1.006 mm/m
  against +0.005 mm/m at 80 km/h;
* but it is negative where the predicate demanded positive, so ``H8_lateral_registration`` is False;
* the sign convention is itself suspect: round 74 measured ``d(lever_y)/dq[y] = -1`` (a positive wheelset y
  moves the contact to smaller absolute y), so a *negative* q[y] is the outboard side, which is where the
  blade is.  Under that reading the mechanism survives and the *predicate*, not the physics, was wrong.

Because that is a claim about a convention, it is not turned into a pass here.  What is pinned instead: the
numbers, the drift, and the fact that the verdict is False, so that the next round has to re-register the
predicate (or run the convention-free test: seat the station with the measured displacement imposed and see
whether the share reaches 5 %).

The 100 km/h column of round 307 is pinned here as well, because it is the third point of the same table and
it was predicted (0.008 m) before it was measured.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import s160_engage_registration as reg  # noqa: E402

REPORTS = ROOT / "reports" / "load_split_inversion_2026-10-31"
REGISTRATION = REPORTS / "engage_registration.json"
GAP_100 = REPORTS / "effective_gap_100.json"


@pytest.fixture(scope="module")
def report() -> dict:
    assert REGISTRATION.is_file(), f"missing {REGISTRATION}"
    return json.loads(REGISTRATION.read_text(encoding="utf-8"))


def _value(report: dict, speed: float, station: float) -> float:
    return report["rows"][str(float(speed))][f"{station:.3f}"]


def test_the_three_speeds_are_read_and_pinned(report: dict) -> None:
    assert set(report["rows"]) == {"60.0", "80.0", "100.0"}
    assert _value(report, 80.0, 58.15) == pytest.approx(-3.954e-4, abs=5e-7)
    assert _value(report, 60.0, 58.15) == pytest.approx(-3.4915e-3, abs=5e-6)
    assert _value(report, 100.0, 58.15) == pytest.approx(-7.213e-4, abs=5e-7)
    assert report["constants"]["axle_offset_m"] == pytest.approx(10.0)
    assert report["constants"]["target_station_m"] == pytest.approx(58.150)


def test_sixty_drifts_laterally_and_eighty_does_not(report: dict) -> None:
    drift = {speed: row["drift_m_per_m"] for speed, row in report["runs"].items()}
    assert drift["60.0"] < -0.5e-3, "the 60 km/h run has to drift inboard by more than half a mm per metre"
    assert abs(drift["80.0"]) < 0.05e-3
    assert abs(drift["100.0"]) < 0.1e-3
    # The drift is what makes the 60 km/h displacement grow along the switch.
    early = _value(report, 60.0, 57.4)
    late = _value(report, 60.0, 59.2)
    assert late < early - 1.0e-3


def test_the_displacement_is_large_but_the_predicate_refused(report: dict) -> None:
    delta = report["deltas_m"]["60_vs_80"]
    threshold = report["constants"]["min_displacement_m"]
    assert threshold == pytest.approx(0.20e-3)
    assert delta == pytest.approx(-3.096e-3, abs=2e-5)
    assert abs(delta) > 10.0 * threshold, "the size test passed by an order of magnitude"
    assert delta < 0.0, "and yet the sign was the registered opposite"
    assert report["H8_lateral_registration"] is False


def test_the_predicate_arithmetic_is_what_refused(report: dict) -> None:
    """H8 is a sign test, so flipping the sign in the data would have confirmed it: pin the rule."""
    threshold = report["constants"]["min_displacement_m"]
    delta = report["deltas_m"]["60_vs_80"]
    assert (delta >= threshold) is False
    assert ((-delta) >= threshold) is True, "the same magnitude on the other side would have passed"
    assert reg.MIN_DISPLACEMENT_M == pytest.approx(threshold)


def test_the_hundred_kmh_column_was_predicted_and_passed() -> None:
    assert GAP_100.is_file(), f"missing {GAP_100}"
    verdict = json.loads(GAP_100.read_text(encoding="utf-8"))["verdict"]
    assert verdict["measured_engage_5pct_m"] == pytest.approx(58.153)
    assert verdict["station_from_effective_m"] == pytest.approx(58.145, abs=5e-4)
    assert verdict["station_error_m"] == pytest.approx(0.008, abs=2e-3)
    assert verdict["H7_reference_station"] is True
