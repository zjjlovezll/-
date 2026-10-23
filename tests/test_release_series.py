"""发布序列表必须与 git 标签、发布说明保持一致（漂移守卫）。"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "docs" / "RELEASE_SERIES.md"
SCRIPT = REPO / "scripts" / "release_series.py"


def _module():
    spec = importlib.util.spec_from_file_location("release_series", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_series"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _tags() -> list[str]:
    result = subprocess.run(["git", "tag", "--list", "v*"], cwd=REPO, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        pytest.skip("不是 git 检出，无法核对标签")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_the_document_exists_and_is_generated() -> None:
    assert DOC.is_file(), "缺少 docs/RELEASE_SERIES.md（跑 scripts/release_series.py）"
    text = DOC.read_text(encoding="utf-8")
    assert "由脚本生成" in text
    assert "| 版本 | 打标签时间 | 提交 | 一句话 | 发布说明 |" in text


def test_the_document_matches_the_tags() -> None:
    if not _tags():
        pytest.skip("没有标签")
    module = _module()

    assert DOC.read_text(encoding="utf-8") == module.render(), (
        "docs/RELEASE_SERIES.md 与 git 标签不一致：跑 python -X utf8 scripts/release_series.py")


def test_every_tag_gets_a_row() -> None:
    tags = _tags()
    if not tags:
        pytest.skip("没有标签")
    text = DOC.read_text(encoding="utf-8")

    for tag in tags:
        assert re.search(rf"^\| {re.escape(tag.lstrip('v'))} \|", text, re.MULTILINE), tag


def test_every_release_note_is_referenced() -> None:
    text = DOC.read_text(encoding="utf-8")
    notes = sorted(p.name for p in (REPO / "docs").glob("RELEASE_NOTES_*.md"))

    assert notes, "一份发布说明都没有？"
    for name in notes:
        assert f"({name})" in text or name in text, f"{name} 没出现在发布序列表里"


def test_rows_are_in_version_order() -> None:
    module = _module()
    versions = [row[0] for row in module.rows()]

    assert versions == sorted(versions, key=module._version_key)


def test_the_check_mode_agrees_with_the_file() -> None:
    module = _module()

    # --check 是闸门用的：内容一致返回 0，不一致返回 2（不写盘）。
    assert module.main(["--check"]) == 0
