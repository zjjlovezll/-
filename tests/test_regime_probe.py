"""The 60 km/h blade load sits in a different contact regime, and the report has to say so."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.corpus

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "regime_probe.json"


@pytest.fixture(scope="module")
def report() -> dict:
    if not REPORT.is_file():
        pytest.skip("run scripts/s148_regime_probe.py first")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_seated_blade_is_idle_while_the_rolling_one_carries(report: dict) -> None:
    static, dynamic = report["static"], report["dynamic"]
    assert static["residual_n"] < 1e-5
    assert static["blade_n"] <= 1.0, "the seated blade must not carry at 54 m"
    assert dynamic["bodies"]["blade"]["force_n"] > 2.0e4
    assert dynamic["bodies"]["stock"]["force_n"] > 2.0e4
    total = dynamic["bodies"]["stock"]["force_n"] + dynamic["bodies"]["blade"]["force_n"]
    assert abs(total - dynamic["rail_force_n"]) <= 1e-6 * dynamic["rail_force_n"]


def test_the_two_contacts_are_not_a_tread_transfer(report: dict) -> None:
    geometry = report["geometry"]
    assert geometry["lateral_separation_m"] > 1.0e-3
    assert geometry["wheel_surface_drop_m"] > 1.5e-3
    assert geometry["slope"] > 1.5
    assert geometry["tread_could_supply"] is False
    assert report["regime"] == "flange_root"


def test_the_crown_step_is_the_drawn_one(report: dict) -> None:
    # 54.0 m: stock crown +72.4 um, blade crown -2402.0 um, straight off the case geometry.
    assert report["crown_step_m"] == pytest.approx(2.4744e-3, abs=1e-6)


def test_the_verdict_refuses_to_claim_an_amplitude(report: dict) -> None:
    verdict = report["verdict"]
    lowered = verdict.lower()
    assert "flange_root" in lowered
    for banned in ("amplitude is", "recovered", "accurate", "validated"):
        assert banned not in lowered
    assert report["not_measured"], "the probe must name what it did not measure"
    assert "wheel" in report["not_measured"].lower()
