"""The self-check has to be right about what is missing, not just cheerful.

These tests never need a corpus or a display: ``collect()`` is split from ``report()`` so each check
can be exercised with a broken environment instead of the developer's working one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from velch import selfcheck

SOURCE = Path(__file__).resolve().parent.parent / "src" / "velch" / "selfcheck.py"


def test_collect_reports_every_area_the_user_needs():
    names = [row.name for row in selfcheck.collect()]

    for expected in ("版本与发布说明", "算例语料", "Tk 界面库", "绘图库 matplotlib", "Simpack 模型", "可写目录"):
        assert expected in names, f"{expected} is not checked"


def test_report_separates_what_blocks_from_what_is_optional():
    checks = [
        selfcheck.Check("甲", selfcheck.PASS, "好"),
        selfcheck.Check("乙", selfcheck.WARN, "缺一点", "这样补"),
    ]
    text = selfcheck.report(checks)

    assert "[PASS] 甲" in text
    assert "[WARN] 乙" in text
    assert "→ 这样补" in text
    assert "可以启动" in text


def test_a_failed_check_makes_the_whole_report_a_failure():
    checks = [selfcheck.Check("甲", selfcheck.FAIL, "坏了", "修它")]

    assert "1 项必须修" in selfcheck.report(checks)
    assert all(row.ok for row in checks) is False


def test_missing_corpus_is_a_failure_that_carries_the_hint(tmp_path):
    """A wrong VELCH_DATA_ROOT is the single most common first-run problem."""

    from velch import data_root

    monkey_env = {"VELCH_DATA_ROOT": str(tmp_path / "nowhere")}
    previous = {key: __import__("os").environ.get(key) for key in monkey_env}
    __import__("os").environ.update(monkey_env)
    try:
        check = selfcheck._corpus_check()
    finally:
        for key, value in previous.items():
            if value is None:
                __import__("os").environ.pop(key, None)
            else:
                __import__("os").environ[key] = value

    assert check.status == selfcheck.FAIL
    assert "nowhere" in check.detail
    assert "VELCH_DATA_ROOT" in check.fix or "标记" in check.fix
    assert data_root is not None


def test_a_simpack_path_that_no_longer_exists_is_a_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("VELCH_SIMPACK_MODEL", str(tmp_path / "gone.spck"))
    monkeypatch.setenv("VELCH_SIMPACK_ROOT", str(tmp_path))

    check = selfcheck._simpack_check()

    assert check.status == selfcheck.FAIL
    assert "gone.spck" in check.detail


def test_simpack_is_optional_not_broken(monkeypatch):
    monkeypatch.delenv("VELCH_SIMPACK_MODEL", raising=False)
    monkeypatch.delenv("VELCH_SIMPACK_ROOT", raising=False)

    check = selfcheck._simpack_check()

    assert check.status == selfcheck.WARN
    assert check.ok is True


def test_json_output_carries_the_same_records(monkeypatch, capsys):
    monkeypatch.setattr(selfcheck, "collect", lambda: [selfcheck.Check("甲", selfcheck.PASS, "好")])

    assert selfcheck.main(["--json"]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out.strip().splitlines()[-1])

    assert payload["checks"][0]["name"] == "甲"
    assert payload["checks"][0]["status"] == "pass"


def test_exit_code_is_two_when_something_must_be_fixed(monkeypatch, capsys):
    monkeypatch.setattr(selfcheck, "collect", lambda: [selfcheck.Check("甲", selfcheck.FAIL, "坏了")])

    assert selfcheck.main([]) == 2
    assert "必须修" in capsys.readouterr().out


def test_the_selfcheck_does_not_drag_in_the_solver():
    """It has to answer in a broken install, so it may not import the forward stack."""

    text = SOURCE.read_text(encoding="utf-8")

    for forbidden in ("vehicle_solver", "velch.contact", "jacobian"):
        assert forbidden not in text, f"selfcheck must not import {forbidden}"


def test_the_cli_exposes_it():
    from velch import cli

    text = Path(cli.__file__).read_text(encoding="utf-8")

    assert '"selfcheck"' in text
    assert "selfcheck" in text

def test_a_frozen_build_looks_for_docs_under_internal(monkeypatch, tmp_path):
    """PyInstaller 6 puts datas under _internal, so the exe's folder alone is not enough."""

    from velch import data_root

    monkeypatch.setattr(data_root, "is_frozen", lambda: True, raising=False)
    monkeypatch.setattr(data_root, "frozen_install_root", lambda: tmp_path, raising=False)

    roots = selfcheck._docs_roots()

    assert tmp_path in roots
    assert tmp_path / "_internal" in roots
    assert len(roots) == len(set(roots)), "the same folder twice reads like a defect"
