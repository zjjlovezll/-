"""The evidence map must not become another list that quietly goes stale."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MAP = REPO / "docs" / "EVIDENCE_MAP.md"

SECTIONS = ("① 代码整理与稳定", "①b 发布物与标签一致", "② 全仓 bug 清理",
            "③ 界面美观与可读性", "④ 安装包", "⑤ 读取 Simpack 模型", "物理数值不变")


@pytest.fixture(scope="module")
def text() -> str:
    assert MAP.is_file(), "docs/EVIDENCE_MAP.md 不存在：跑 python scripts/evidence_map.py"
    return MAP.read_text(encoding="utf-8")


def test_it_covers_every_objective_item(text: str) -> None:
    missing = [name for name in SECTIONS if name not in text]
    assert not missing, f"证据地图缺少分项：{missing}"


def test_every_linked_artifact_exists(text: str) -> None:
    """A map that points at a deleted file is worse than no map."""

    broken = [target for target in re.findall(r"\]\(\.\./([^)]+)\)", text)
              if not (REPO / target).exists()]
    assert not broken, f"引用已不存在：{broken}"


def test_every_command_names_a_file_that_exists(text: str) -> None:
    broken: list[str] = []
    for command in re.findall(r"`(python -X utf8 [^`]+)`", text):
        for token in command.split():
            if token.startswith(("scripts/", "packaging/")) and not (REPO / token).exists():
                broken.append(token)
    assert not broken, f"命令里的文件不存在：{broken}"


def test_each_row_carries_a_command_and_an_expectation(text: str) -> None:
    rows = [line for line in text.splitlines() if line.startswith("| **")]
    assert len(rows) == len(SECTIONS)
    for row in rows:
        assert "`python -X utf8" in row, f"没有复核命令：{row[:60]}"
        assert "期望：" in row, f"没有期望结果：{row[:60]}"


def test_it_states_what_is_not_covered(text: str) -> None:
    """The honest part: calibration, signature, the read-only ACL case."""

    assert "不在这张表里的东西" in text
    assert "unvalidated_against_measurement_or_Simpack" in text
    assert "未签名" in text


def test_the_generated_check_agrees(text: str) -> None:  # noqa: ARG001 - fixture keeps ordering
    """``scripts/evidence_map.py --check`` is the same check, so the two cannot disagree."""

    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "evidence_map", REPO / "scripts" / "evidence_map.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.path.insert(0, str(REPO / "src"))
    spec.loader.exec_module(module)
    assert module.check() == 0

def test_with_run_is_a_flag_and_reaches_the_simpack_row() -> None:
    """``--with-run`` must exist *and* be threaded into the ⑤ row builder.

    The row used to stop at ``geometry_readable``; a flag that exists but is never passed down
    would look identical from the outside and quietly regress to catalog-only evidence.
    """

    source = (REPO / "scripts" / "evidence_map.py").read_text(encoding="utf-8")
    assert '"--with-run"' in source
    assert "def build(with_run: bool = False)" in source
    assert "_simpack(with_run)" in source
    assert "run-vehicle" in source and "simpack-case" in source


def test_with_run_says_so_when_the_template_is_missing(monkeypatch) -> None:
    """Without ``VELCH_EVIDENCE_TEMPLATE`` the row must say what is missing, not pretend."""

    from scripts.evidence_map import _simpack  # type: ignore[import-not-found]

    monkeypatch.setenv("VELCH_SIMPACK_MODEL", "")
    monkeypatch.setenv("VELCH_SIMPACK_ROOT", "")
    text = _simpack(with_run=True)
    assert "VELCH_SIMPACK_MODEL" in text
