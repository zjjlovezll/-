"""发布证据窗口：能定位、能显示、找不到时说清楚查过哪里。"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from velch.ui import evidence_map_dialog as dialog_module


def test_it_finds_the_checkout_map() -> None:
    path = dialog_module.locate_evidence_map()

    assert path is not None, "源码工作区里必须有 docs/EVIDENCE_MAP.md"
    assert path.name == "EVIDENCE_MAP.md"
    body = path.read_text(encoding="utf-8")
    assert "凭什么可以说" in body and "逐项证据" in body


def test_a_missing_file_names_the_places_it_looked(monkeypatch) -> None:
    monkeypatch.setattr(dialog_module, "docs_roots", lambda: [Path(r"F:\nowhere")])

    assert dialog_module.locate_evidence_map() is None
    text = dialog_module.describe(None)
    assert "未找到" in text and "nowhere" in text and "evidence_map.py" in text


def test_describe_reports_time_and_size(tmp_path) -> None:
    path = tmp_path / "EVIDENCE_MAP.md"
    path.write_text("x" * 2048, encoding="utf-8")

    text = dialog_module.describe(path)

    assert "KB" in text and str(tmp_path) in text


def _make_root() -> tk.Tk:
    """同一进程里多次建根时 Tk 偶发 ``invalid command name "tcl_findLibrary"``；重试即可。"""

    import time

    last: Exception | None = None
    for attempt in range(4):
        try:
            root = tk.Tk()
            root.withdraw()
            return root
        except tk.TclError as error:  # pragma: no cover - 依赖进程状态
            last = error
            time.sleep(0.2 * (attempt + 1))
    pytest.fail(f"Tk 不可用：{last}")


@pytest.fixture()
def application():
    root = _make_root()
    from velch.ui import app as app_module

    instance = app_module.VelchUI(root, headless=True)
    yield instance
    root.destroy()


def test_the_dialog_shows_the_file_read_only(application) -> None:
    dialog = dialog_module.EvidenceMapDialog(application.root)
    try:
        body = dialog.text.get("1.0", "end")
        assert "逐项证据" in body
        assert str(dialog.text.cget("state")) == "disabled"
    finally:
        dialog.destroy()


def test_the_header_offers_the_evidence_button() -> None:
    source = Path(dialog_module.__file__).with_name("app.py").read_text(encoding="utf-8")

    assert '"发布证据"' in source
    assert "def show_evidence" in source
