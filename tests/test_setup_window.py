"""The reading window has one validator, and a run that cannot reach it is refused.

The reviewer found three ways for a typo to become a physics conclusion: the setup loader accepted a
window typed backwards, silently dropped a third mileage, and raised ``IndexError`` for a
single-element list.  Round 315 also measured a fourth: the shipped setup declared a 9 m window on a
0.02 s run, so the run sampled 4.9 % of it and gate 9 passed on that fraction.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from velch import setup as window_rules

ROOT = pathlib.Path(__file__).resolve().parents[1]
SETUPS = ROOT / "setups"


def test_one_validator_rejects_every_shape_that_is_not_two_ordered_mileages() -> None:
    assert window_rules._window("w", None) is None
    assert window_rules._window("w", [56.0, 65.0]) == (56.0, 65.0)
    assert window_rules._window("w", (56, 65)) == (56.0, 65.0)
    for bad in ([65.0, 56.0], [56.0], [56.0, 65.0, 70.0], 56.0, "56-65", []):
        with pytest.raises(ValueError):
            window_rules._window("w", bad)


def test_the_setup_loader_uses_that_validator(tmp_path) -> None:
    raw = json.loads((SETUPS / "one_set_reading.json").read_text(encoding="utf-8"))
    raw["case"] = str((ROOT / raw["case"]).resolve())
    broken = dict(raw, stationarity_window_m=[65.0, 56.0])
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(ValueError, match="start < end"):
        window_rules.load_setup(path)
    good = tmp_path / "good.json"
    good.write_text(json.dumps(raw), encoding="utf-8")
    assert window_rules.load_setup(good).stationarity_window_m == (56.0, 65.0)


def test_a_run_too_short_to_reach_the_window_is_refused_before_it_starts() -> None:
    """0.405 s at 60 km/h covers 6.75 m of the 9 m window: that cannot be a stationarity claim."""
    setup = window_rules.load_setup(SETUPS / "one_set_reading.json")
    assert setup.stationarity_window_m == (56.0, 65.0)
    with pytest.raises(ValueError, match="too short for the declared reading window"):
        window_rules.resolve(setup, ["speed.kmh=60"])


def test_the_smoke_setup_makes_no_window_claim_and_so_gets_no_gate() -> None:
    setup = window_rules.load_setup(SETUPS / "one_set_straight.json")
    resolved = window_rules.resolve(setup)
    assert resolved.setup.stationarity_window_m is None
    assert resolved.case.run.stationarity_window_m is None
    # Writing a null key would have changed case_sha256 and split this setup's archive from the
    # identical earlier runs; only a claimed window is materialised.
    assert resolved.case_path is not None
