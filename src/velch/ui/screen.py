"""The screen contract shared by all six screens.

A screen owns its widgets, knows how to (re)load its data, and reports what it loaded so
``--selftest`` can print real numbers instead of "it opened".  Nothing here imports
Matplotlib or starts a solver.
"""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk
from typing import Any

from . import theme
from .widgets import count_widgets


@dataclass
class ScreenStats:
    """What a screen actually put on screen, reported by ``--selftest``."""

    name: str
    title: str
    controls: int = 0
    rows: int = 0
    detail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def line(self) -> str:
        head = f"{self.name:<11} 控件 {self.controls:>4}  数据行 {self.rows:>5}  {self.detail}"
        return head + (f"  [错误] {self.error}" if self.error else "")


class Screen(ttk.Frame):
    """Base class: lazy first load, explicit refresh, measurable widget tree."""

    name = ""
    title = ""
    subtitle = ""
    shortcut = ""
    hint = ""

    def __init__(self, parent: tk.Misc, app: Any):
        super().__init__(parent, style="Bg.TFrame", padding=(theme.PAD_LG, theme.PAD))
        self.app = app
        self._loaded = False
        self._rows = 0
        self._detail = ""
        self._error = ""
        self._build()

    # -- subclass hooks ----------------------------------------------------
    def _build(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def refresh(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def selftest_detail(self) -> str:
        return self._detail

    # -- lifecycle ---------------------------------------------------------
    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.reload()

    def reload(self) -> None:
        self._error = ""
        try:
            self.refresh()
            self._loaded = True
        except Exception as exc:  # a broken screen must not take the window down
            self._error = f"{type(exc).__name__}: {exc}"
            self.app.set_status(f"{self.title} 加载失败：{self._error}", tone="fail")
        self.app.refresh_status()

    def on_show(self) -> None:
        self.ensure_loaded()

    def on_hide(self) -> None:
        return None

    # -- reporting ---------------------------------------------------------
    def set_rows(self, rows: int, detail: str = "") -> None:
        self._rows = rows
        if detail:
            self._detail = detail

    def stats(self) -> ScreenStats:
        return ScreenStats(name=self.name, title=self.title,
                           controls=count_widgets(self), rows=self._rows,
                           detail=self.selftest_detail(), error=self._error)

    # -- shared building blocks -------------------------------------------
    def section(self, parent: tk.Misc, text: str) -> ttk.Label:
        return ttk.Label(parent, text=text, style="Section.TLabel")

    def explain(self, parent: tk.Misc, text: str) -> ttk.Label:
        return ttk.Label(parent, text=text, style="Dim.TLabel", wraplength=760,
                         justify="left")


class PlaceholderScreen(Screen):
    """Used only when a screen module fails to import, so the app still opens."""

    def __init__(self, parent: tk.Misc, app: Any, *, name: str, title: str, reason: str):
        self.name, self.title = name, title
        self._reason = reason
        super().__init__(parent, app)

    def _build(self) -> None:
        ttk.Label(self, text=self.title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text=self._reason, style="Muted.TLabel", wraplength=760,
                  justify="left").pack(anchor="w", pady=theme.SPACE["3"])

    def refresh(self) -> None:
        self._detail = self._reason
