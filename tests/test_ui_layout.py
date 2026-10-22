"""Every button must be at least as wide as its own text says it is, and every
screen must load without reporting a failure.

The ② 运行 screen once shipped four buttons that were mapped at 13 px instead of 35 — the "start a
run" button existed but nobody could see it.  A screenshot caught it; a measurement would have.  So
this test maps each screen for real and compares every button's allocated width against the width
Tk asked for, at 100 % and 130 % type size.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from velch.ui import app as app_module
from velch.ui import theme

TOLERANCE = 2  # Tk rounds allocations; a clipped button loses far more than 2 px


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _buttons(screen) -> list[tk.Misc]:
    return [w for w in _walk(screen)
            if isinstance(w, (tk.ttk.Button, tk.ttk.Checkbutton))]


@pytest.fixture(scope="module")
def application():
    try:
        root = tk.Tk()
    except tk.TclError:  # pragma: no cover - no display
        root = _make_root(tk)
    root.geometry("1360x860")
    app = app_module.VelchUI(root)
    root.update()
    yield app
    try:
        root.destroy()
    except tk.TclError:  # pragma: no cover - already gone
        pass


def _measure(application, screen_name: str) -> list[tuple[str, int, int]]:
    application.show(screen_name)
    application.root.update_idletasks()
    application.root.update()
    screen = application.screens[screen_name]
    screen.reload()
    application.root.update_idletasks()
    application.root.update()
    return [(str(button.cget("text")), button.winfo_width(), button.winfo_reqwidth())
            for button in _buttons(screen)]


@pytest.mark.parametrize("scale", [1.0, 1.3])
def test_no_button_is_narrower_than_its_label(application, scale: float) -> None:
    original = theme.SCALE
    try:
        if scale != original:
            application.zoom(0.0, absolute=scale)
            application.root.update()
        problems: list[str] = []
        checked = 0
        for name, *_ in app_module.SCREENS:
            for text, width, required in _measure(application, name):
                checked += 1
                if width + TOLERANCE < required:
                    problems.append(f"{name}: 「{text}」 {width}px < required {required}px")
        assert checked >= 25, f"only {checked} buttons measured; the screens did not build"
        assert not problems, "clipped buttons:\n" + "\n".join(problems)
    finally:
        if theme.SCALE != original:
            application.zoom(0.0, absolute=original)
            application.root.update()


def test_every_screen_builds_without_error(application) -> None:
    """A screen that throws while building would show an empty frame and no test failure.

    ``Screen.reload`` catches the exception and writes 「该屏加载失败」, so "the widget tree is not
    empty" proves nothing — the ⑦ 三维 screen shipped a ``KeyError: 0`` that way and the file-level
    test stayed green.  Read the text instead.
    """
    problems: list[str] = []
    for name, *_ in app_module.SCREENS:
        application.show(name)
        application.root.update_idletasks()
        application.root.update()
        screen = application.screens[name]
        assert screen.winfo_children(), f"{name} built no widgets"
        assert screen.selftest_detail() is not None
        texts = [str(w.cget("text")) for w in _walk(screen) if "text" in w.keys()]
        texts += [str(w.cget("textvariable")) for w in _walk(screen)
                  if "textvariable" in w.keys()]
        for text in texts:
            if "加载失败" in text:
                problems.append(f"{name}: {text}")
        for widget in _walk(screen):
            if isinstance(widget, tk.ttk.Label):
                value = widget.cget("text")
                if isinstance(value, str) and "加载失败" in value:
                    problems.append(f"{name}: {value}")
    assert not problems, "screens reported a load failure:\n" + "\n".join(problems)


def test_the_layout_test_can_see_a_clipped_button(application) -> None:
    """Guard against a measurement that always passes: shrink a button and expect to see it."""
    application.show("cases")
    application.root.update()
    screen = application.screens["cases"]
    buttons = _buttons(screen)
    assert buttons, "no buttons on ① 算例"
    button = buttons[0]
    requested = button.winfo_reqwidth()
    assert button.winfo_width() + TOLERANCE >= requested
    # A 1 px wide button against a request of ~200 px is exactly the failure mode we are guarding.
    assert 1 + TOLERANCE < requested


def _make_root(tk):
    """A Tk root, retried: a second interpreter can fail while another test still holds one.

    Skipping on the first TclError is how "all screens green" and "one random test skipped"
    coexisted. Retry, then decide: ``VELCH_HEADLESS=1`` means this machine really has no display.
    """

    last = None
    for _attempt in range(3):
        try:
            return tk.Tk()
        except tk.TclError as error:  # pragma: no cover - headless only
            last = error
            time.sleep(0.2)
    if os.environ.get("VELCH_HEADLESS"):
        pytest.skip(f"headless: {last}")
    pytest.fail(f"Tk could not open a window after 3 tries: {last} "
                "(set VELCH_HEADLESS=1 if this machine really has no display)")
