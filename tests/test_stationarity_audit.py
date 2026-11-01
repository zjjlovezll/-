"""Tests for `scripts/s164_stationarity_audit.py`.

The audit exists because the seven numerical gates do not test whether a run has settled: the 60 km/h archive
passes all seven while its front-rail load swings between 0 and 208 kN.  These tests pin what the audit found,
and -- just as important -- that the audit would have caught the failure it was written for.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import s164_stationarity_audit as audit_module  # noqa: E402


REPORT = audit_module.REPORT
CHATTERED = "one_set_x46-060.00kmh-0.5400s-500us-83e727fc"


@pytest.fixture(scope="module")
def report() -> dict:
    assert REPORT.is_file(), "run scripts/s164_stationarity_audit.py first"
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.mark.corpus
def test_the_slow_archive_is_quarantined_and_nothing_else_is(report: dict) -> None:
    verdict = report["verdict"]
    assert verdict["runs"] == 63
    assert verdict["quarantined"] == ["one_set_x46-060.00kmh-0.0200s-500us-83e727fc", CHATTERED]
    assert verdict["stationary"] == 61
    rows = {row["run_id"]: row for row in report["rows"]}
    slow = rows[CHATTERED]
    assert slow["max_rail_std_kn"] > 30.0
    assert slow["worst_rail"] == "axle1_right"
    # the failure mode was a modal transient that never decayed, not a wrong load
    assert slow["modal_decay"] > 0.7


@pytest.mark.corpus
def test_every_gate_bearing_run_holds_its_load(report: dict) -> None:
    """The 80 and 100 km/h gate rows stay quotable; the audit must not take them down with the slow one."""

    rows = {row["run_id"]: row for row in report["rows"]}
    for run_id in ("one_set_bump060.0um-100.00kmh-0.6000s-500us-541e67fa",
                   "one_set_x46_bump060.0um-100.00kmh-0.3300s-500us-83eb7b5d",
                   "one_set_threepeak-080.00kmh-0.6000s-500us-d902d422",
                   "one_set_random-080.00kmh-0.6000s-500us-2f516e4b"):
        assert rows[run_id]["stationary"] is True, run_id
        assert rows[run_id]["max_rail_std_kn"] < 1.0, run_id
    # and the quarantined pair is exactly the "gates all true but not stationary" set
    assert report["verdict"]["all_gates_true_but_not_stationary"] == report["verdict"]["quarantined"]


@pytest.mark.corpus
def test_one_answer_per_route_and_speed_uses_the_longest_archive(report: dict) -> None:
    summary = report["verdict"]["by_route_speed"]
    assert summary["one_set_x46|60"]["duration_s"] == pytest.approx(0.54)
    assert summary["one_set_x46|60"]["stationary"] is False
    assert summary["one_set_x46|80"]["stationary"] is True
    assert summary["one_set_x46_bump060.0um|100"]["stationary"] is True
    # the growing modal block at 100 km/h is recorded rather than hidden, even though the force is quiet
    assert summary["one_set_x46_bump060.0um|100"]["modal_decay"] > 2.0


def test_the_predicate_rejects_the_measured_failure_and_accepts_the_quiet_rows() -> None:
    assert audit_module.is_stationary(34.75) is False
    assert audit_module.is_stationary(6.0) is False
    assert audit_module.is_stationary(0.51) is True
    assert audit_module.is_stationary(0.07) is True
    # the threshold is where it says it is, on both sides
    assert audit_module.is_stationary(audit_module.MAX_STD_KN) is False
    assert audit_module.is_stationary(audit_module.MAX_STD_KN - 1e-9) is True


def test_the_gate_page_refuses_a_row_whose_run_did_not_settle(tmp_path: pathlib.Path) -> None:
    """A row that says "stationary: False" must not be quotable, whatever its gates say."""

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
    import s156_gate_page as page

    table = {
        "60": {"status": "measured", "gates": {"all_passed": True}, "stationary": False,
               "stationary_bump": None, "gates_quotable": False,
               "physical_error_m": {"0.05": 0.267}},
        "80": {"status": "measured", "gates": {"all_passed": True}, "stationary": True,
               "stationary_bump": True, "gates_quotable": True,
               "physical_error_m": {"0.05": 0.423}},
    }
    verdict = page.verdict(table)
    assert verdict["not_stationary"] == ["60"]
    assert verdict["gates_quotable"] == {"60": False, "80": True}
