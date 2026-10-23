"""已知未修项：模块里的 id 与 `docs/BUGS.md` 的 O 行必须一一对上。"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from velch import open_items as items
from velch.ui import open_items_dialog as dialog

REPO = Path(__file__).resolve().parent.parent
BUGS = REPO / "docs" / "BUGS.md"


def _ledger_ids() -> set[str]:
    text = BUGS.read_text(encoding="utf-8")
    rows = set(re.findall(r"^\|\s*(O\d{3})", text, re.MULTILINE))
    headings = set(re.findall(r"^##\s*(O\d{3})\b", text, re.MULTILINE))
    return rows | headings


def test_every_module_item_is_in_the_ledger() -> None:
    ledger = _ledger_ids()
    missing = [item.id for item in items.ITEMS if item.id not in ledger]

    assert not missing, f"这些条目只在代码里，账本没记：{missing}"


def test_every_ledger_id_is_in_the_module() -> None:
    known = {item.id for item in items.ITEMS}
    missing = sorted(_ledger_ids() - known)

    assert not missing, f"账本里的这些 id 代码里没有：{missing}"


def test_ids_are_unique_and_shaped_like_the_ledger() -> None:
    ids = [item.id for item in items.ITEMS]

    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"O\d{3}", item_id) for item_id in ids)


def test_open_items_excludes_closed_ones() -> None:
    opened = {item.id for item in items.open_items()}

    assert opened == {item.id for item in items.ITEMS if item.status != "closed"}
    assert "O006" not in opened, "O006 已在 0.4.10 实现，不该再算未修"
    assert "O003" not in opened, "O003 已在 0.4.22 实现"


def test_a_deliberate_limitation_is_not_counted_as_a_bug() -> None:
    # O005 是设计约束：Simpack 侧物理量不自动映射。它要显示，但不该算进"待修"数字。
    assert items.by_id("O005").status == "by_design"
    assert items.counts()["open"] == 2


def test_every_item_says_why_and_when() -> None:
    for item in items.ITEMS:
        assert len(item.title) >= 6, item.id
        assert len(item.why) >= 30, f"{item.id} 的解释太短，读的人不知道该怎么处理"
        assert item.since, f"{item.id} 没有记录版本"


def test_the_dialog_outline_names_every_item() -> None:
    text = "\n".join(dialog.outline())

    for item in items.ITEMS:
        assert f"[{item.id}]" in text
    assert "设计约束" in text
    assert items.LEDGER in text


def test_the_summary_line_admits_how_many_are_open() -> None:
    text, tone = items.summary_text()

    assert "已知未修" in text
    assert str(items.counts()["open"]) in text
    assert tone in {"warn", "pass"}


def test_the_dialog_does_not_import_the_forward_stack() -> None:
    source = Path(dialog.__file__).read_text(encoding="utf-8")

    for forbidden in ("vehicle_solver", "velch.contact", "jacobian", "simulate_vehicle"):
        assert forbidden not in source


@pytest.mark.parametrize("item_id", ["O001", "O005", "O008"])
def test_the_still_open_ids_are_exactly_these(item_id: str) -> None:
    # 钉住集合：关掉一项是件值得改测试的事，不是悄悄消失。
    assert items.by_id(item_id).status in {"open", "by_design"}
