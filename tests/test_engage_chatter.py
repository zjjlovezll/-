"""Pin the withdrawal: the 60 km/h archive never settles, so its crossing is not a measurement.

Rounds 304-309 built a three-speed location table and kept chasing the slowest row's disagreement.  Round 310
found that the row was not a measurement at all: the run starts with the modal block displaced and rings for the
whole 0.54 s, so its front-rail normal force swings from 0 to 208 kN (standard deviation 34.75 kN) while the other
two hold 60.1 kN to within 0.07 and 0.51 kN.

Everything here is a guard against quietly restoring the withdrawn numbers:

* the stationarity separation (34.75 against 0.07 and 0.51 kN) and the blade's nine on/off crossings;
* the modal-block evidence (initial norm 5.50x the others, still 0.748 of it at the end -- no decay);
* the two claims C1 and C2, and the exact list of withdrawn statements;
* the gate page carries the flag, so a row that is not stationary cannot be printed as if it were quotable;
* and a fabricated stationary run must *not* be flagged, so the predicate is not trivially true.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import s156_gate_page as page  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "engage_chatter.json"


@pytest.fixture(scope="module")
def report() -> dict:
    assert REPORT.is_file(), f"missing {REPORT}"
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_the_slow_run_is_two_orders_off_the_others(report: dict) -> None:
    rows = report["rows"]
    assert rows["60"]["loaded_rail_std_kn"] == pytest.approx(34.75, abs=0.05)
    assert rows["80"]["loaded_rail_std_kn"] == pytest.approx(0.071, abs=0.01)
    assert rows["100"]["loaded_rail_std_kn"] == pytest.approx(0.509, abs=0.01)
    low, high = rows["60"]["force_min_max_kn"]["axle1_right"]
    assert low == pytest.approx(0.0, abs=0.01)
    assert high == pytest.approx(207.75, abs=0.05)
    assert rows["60"]["blade_upcrossings_over_1kn"] == 9
    assert rows["80"]["blade_upcrossings_over_1kn"] == 1
    assert report["verdict"]["c1_sixty_not_stationary"] is True


def test_the_cause_is_a_modal_block_that_never_decays(report: dict) -> None:
    verdict = report["verdict"]
    assert verdict["modal_start_ratio_60_over_others"] == pytest.approx(5.50, abs=0.02)
    assert verdict["modal_decay_60"] == pytest.approx(0.748, abs=0.002)
    assert report["rows"]["80"]["modal_norm_m"][-1] / report["rows"]["80"]["modal_norm_m"][0] > 1.0
    assert verdict["c2_modal_transient_unsettled"] is True


def test_the_withdrawn_statements_are_named(report: dict) -> None:
    verdict = report["verdict"]
    assert verdict["valid_speeds_kmh"] == [80.0, 100.0]
    assert len(verdict["withdrawn"]) == 3
    joined = " ".join(verdict["withdrawn"])
    assert "58.000" in joined and "0.145" in joined and "shrinks" in joined
    assert verdict["six_sixty_usable"] is False


def test_the_gate_page_cannot_print_that_row_as_quotable() -> None:
    table = page.measure()
    assert table["60"]["stationary"] is False
    assert table["80"]["stationary"] is True
    assert table["100"]["stationary"] is True
    assert page.verdict(table)["not_stationary"] == ["60"]


def test_a_stationary_run_is_not_flagged(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "chatter.json"
    fake.write_text(json.dumps({"rows": {"60": {"loaded_rail_std_kn": 0.5}}}), encoding="utf-8")
    monkeypatch.setattr(page, "STATIONARITY", fake)
    assert page._stationary(60.0) is True
    fake.write_text(json.dumps({"rows": {"60": {"loaded_rail_std_kn": 6.0}}}), encoding="utf-8")
    assert page._stationary(60.0) is False
    monkeypatch.setattr(page, "STATIONARITY", tmp_path / "absent.json")
    assert page._stationary(60.0) is None
