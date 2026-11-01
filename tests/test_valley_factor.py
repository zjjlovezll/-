"""Pins the valley factorial measured by scripts/s155_valley_factor.py.

The question it settles: why does sliding the fitted centre by +-0.60 m cost 66.7 % of residual rms at
80 km/h but only 11.5 % at 100 km/h (round 301)?  Two candidates, different predictions: the amplitude
(56.6 against 66.2 um) or the background (share field and 496 against 369 usable stations).

Frozen here: the four rises, the 27x background / 0.9x amplitude split, the fact that the share law's
local sensitivity is the same on both backgrounds (so "the share stops responding" is not the mechanism),
the higher residual floor at 100 km/h, and the verdict branches a fabricated table would take.
"""

from __future__ import annotations

import copy
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import s155_valley_factor as valley  # noqa: E402


@pytest.fixture(scope="module")
def table() -> dict:
    return valley.measure()


@pytest.mark.corpus
def test_the_four_rises_reproduce(table: dict) -> None:
    assert table["80@66.22"]["rise"] * 100 == pytest.approx(66.7, abs=0.6)
    assert table["80@56.56"]["rise"] * 100 == pytest.approx(74.3, abs=0.6)
    assert table["100@66.22"]["rise"] * 100 == pytest.approx(2.5, abs=0.3)
    assert table["100@56.56"]["rise"] * 100 == pytest.approx(11.5, abs=0.6)


@pytest.mark.corpus
def test_the_background_dominates_the_amplitude(table: dict) -> None:
    result = valley.verdict(table)
    assert result["dominant"] == "background"
    assert result["background_effect"] > 20.0
    # shrinking the amplitude at the reference background made the valley SHARPER, not flatter
    assert result["amplitude_effect"] < 1.1
    assert table["80@56.56"]["rise"] > table["80@66.22"]["rise"]


@pytest.mark.corpus
def test_the_share_law_still_responds_on_both_backgrounds(table: dict) -> None:
    slow = table["80@66.22"]["d_sigma_per_um"]
    fast = table["100@66.22"]["d_sigma_per_um"]
    assert slow == pytest.approx(fast, rel=0.10), f"local sensitivity differs: {slow} vs {fast}"


@pytest.mark.corpus
def test_the_100_kmh_fit_sits_on_a_higher_residual_floor(table: dict) -> None:
    slow = table["80@66.22"]["base_rms_um"]
    fast = table["100@66.22"]["base_rms_um"]
    assert fast > 1.3 * slow, f"floor ratio only {fast / slow:.2f}"
    # and the absolute cost of sliding is smaller there too, which is why the ratio moves 27x
    assert (table["100@66.22"]["peak_rms_um"] - fast) < 0.25 * (table["80@66.22"]["peak_rms_um"] - slow)


def test_verdict_branches(table: dict) -> None:
    joint = copy.deepcopy(table)
    joint["80@56.56"]["rise"] = table["80@66.22"]["rise"] / 3.0  # amplitude effect 3x, background 27x
    assert valley.verdict(joint)["dominant"] == "joint"

    neither = copy.deepcopy(table)
    neither["100@66.22"]["rise"] = table["80@66.22"]["rise"] / 1.5  # background effect 1.5x
    neither["80@56.56"]["rise"] = table["80@66.22"]["rise"] / 1.5  # amplitude effect 1.5x
    assert valley.verdict(neither)["dominant"] == "neither"
