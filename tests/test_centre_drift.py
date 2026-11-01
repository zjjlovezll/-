"""Pins the centre-drift verdict measured by scripts/s154_centre_drift.py.

What is frozen here, and why each item exists:

* the two centres (80 km/h at 58.514 m, 100 km/h at 58.919 m) -- if either moves, the 0.41 m gap has to
  be re-read before it is quoted anywhere;
* decimation moving a centre by less than 0.10 m -- this is the falsifier that rejected H2, so a change
  in sampling behaviour must break a test rather than slip through as "the gap was sampling after all";
* the gap surviving all three strides -- the property that makes the cross-speed comparison usable;
* the ridge widths from the committed report (80 km/h rises 66.8 % within +-0.6 m, 100 km/h 11.5 %) --
  the mechanism behind the drift, not just its size;
* `verdict()` firing on a fabricated 0.15 m move -- a verdict that cannot fail is not a verdict.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import s154_centre_drift as drift  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "centre_drift.json"


@pytest.fixture(scope="module")
def rows() -> dict:
    return drift.measure()


@pytest.mark.corpus
def test_centres_reproduce(rows: dict) -> None:
    assert rows["80@1"]["centre_m"] == pytest.approx(58.514, abs=0.002)
    assert rows["100@1"]["centre_m"] == pytest.approx(58.919, abs=0.002)
    assert rows["80@1"]["amplitude_um"] == pytest.approx(66.22, abs=0.05)
    assert rows["100@1"]["amplitude_um"] == pytest.approx(56.56, abs=0.05)


@pytest.mark.corpus
def test_decimation_moves_a_centre_by_less_than_the_tolerance(rows: dict) -> None:
    result = drift.verdict(rows)
    assert result["worst_decimation_move_m"] < drift.TOLERANCE_M
    assert result["sampling_is_the_explanation"] is False
    # and the move is far below the gate too, not merely below half of it
    assert result["worst_decimation_move_m"] < drift.GATE_M / 4.0


@pytest.mark.corpus
def test_the_gap_survives_matched_sampling(rows: dict) -> None:
    gaps = drift.verdict(rows)["gap_by_stride_m"]
    assert set(gaps) == {"1", "2", "3"}
    for stride, gap in gaps.items():
        assert gap > drift.GATE_M, f"gap at stride {stride} fell to {gap:.3f} m"
    assert gaps["1"] == pytest.approx(0.406, abs=0.02)


@pytest.mark.corpus
def test_the_100_kmh_valley_is_much_flatter_than_the_80_kmh_one() -> None:
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    ridges = payload["ridges"]
    slow = ridges["80@1"]["peak_rise"]
    fast = ridges["100@1"]["peak_rise"]
    assert slow > 0.40, f"80 km/h ridge lost its sharpness ({slow:.3f})"
    assert fast < 0.15, f"100 km/h ridge is no longer flat ({fast:.3f})"
    assert slow / fast > 4.0
    # the pre-registered flatness threshold is deliberately not met: 100 km/h is 6x flatter, not flat
    assert ridges["100@1"]["valley_is_flat"] is False


def test_verdict_fires_on_a_fabricated_move(rows: dict) -> None:
    poisoned = json.loads(json.dumps(rows))
    poisoned["100@2"]["centre_m"] = poisoned["100@1"]["centre_m"] + 0.15
    assert drift.verdict(poisoned)["sampling_is_the_explanation"] is True
    # a move smaller than the tolerance must not fire
    poisoned["100@2"]["centre_m"] = poisoned["100@1"]["centre_m"] + 0.09
    assert drift.verdict(poisoned)["sampling_is_the_explanation"] is False
