"""The calibration banner: present, permanent, and never turned into a green tick."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from velch.ui import app as app_module
from velch.ui import screen_assess


def test_the_note_states_the_boundary_rather_than_hiding_it() -> None:
    note = screen_assess.CALIBRATION_NOTE

    assert "不是标定" in note
    assert "不能当作对真实道岔的结论" in note
    # 指向两份可查的证据，而不是只说一句免责声明
    assert "docs/BUGS.md" in note and "docs/PHYSICS_INVARIANTS.md" in note


@pytest.fixture()
def application():
    try:
        root = tk.Tk()
    except tk.TclError:  # pragma: no cover - headless CI
        pytest.fail("Tk 不可用：本机的界面测试不该再被跳过")
    root.withdraw()
    instance = app_module.VelchUI(root, headless=True)
    yield instance
    root.destroy()


def test_the_assess_screen_shows_the_note_without_being_asked(application) -> None:
    screen = application.show("assess")

    texts = [str(widget.cget("text")) for widget in _walk(screen) if "text" in widget.keys()]

    assert any("不是标定" in text for text in texts), "横幅必须一进屏就在"


def test_the_note_is_wired_to_the_card_width_it_sits_in() -> None:
    source = Path(screen_assess.__file__).read_text(encoding="utf-8")

    assert "self.wrap_with(self.calibration_label" in source, "写死 wraplength 会在缩放时溢出"
    assert "CALIBRATION_NOTE" in source


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)
