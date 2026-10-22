"""Application shell: window, theme wiring, navigation, state machine, job plumbing.

Layout is a left navigation rail (six screens) + a header strip + the screen body + a
status bar.  The shell owns everything shared:

* the dark theme styles (:meth:`VelchUI.build_style`),
* the screen registry and lazy construction,
* the cross-screen selection context (``run`` / ``case``),
* the single status/state machine (:data:`STATES`),
* one :class:`queue.Queue` that background jobs and subprocess output post into, pumped
  from the Tk event loop so no worker thread ever touches a widget.
"""
from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import ttk
from typing import Any, Callable, Sequence

from . import theme
from .screen import PlaceholderScreen, Screen
from .widgets import Chip, MATPLOTLIB_BACKEND, ui_font

#: Minimum button width in characters.  Windows' vista theme defaults to 11, which in a
#: CJK face reserves ~153 px per button and pushes the last buttons of a row to 1 px.
BUTTON_MIN_CHARS = -3

SCREENS: tuple[tuple[str, str, str, str], ...] = (
    ("cases", "① 算例", "选择、检视与派生算例", "Ctrl+1"),
    ("run", "② 运行", "启动 CLI、跟踪日志、批量并行", "Ctrl+2"),
    ("timeseries", "③ 时程", "多通道曲线与时程缩放", "Ctrl+3"),
    ("spectrum", "④ 频谱", "1/3 倍频程与带宽 RMS", "Ctrl+4"),
    ("assess", "⑤ 评价", "七项数值门与三项限值", "Ctrl+5"),
    ("compare", "⑥ 对照", "与 Simpack / 实测同轴叠加", "Ctrl+6"),
    ("model3d", "⑦ 三维", "钢轨型面与车轮的三维视图", "Ctrl+7"),
)

#: State machine: the header chip and the status bar read the same value.
STATES: dict[str, tuple[str, str]] = {
    "idle": ("空闲", "idle"),
    "running": ("运行中", "run"),
    "failed": ("失败", "fail"),
    "done": ("完成", "pass"),
}

SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("Ctrl+1 … Ctrl+7", "切换到第 1–7 屏"),
    ("F5", "重新加载当前屏"),
    ("Ctrl+R", "在「运行」屏启动所选算例"),
    ("Esc", "取消正在运行的子进程"),
    ("Ctrl+L", "跳到当前屏的筛选/搜索框"),
    ("Ctrl+E", "导出当前图（仅 Matplotlib 后端）"),
    ("Ctrl+= / Ctrl+-", "放大 / 缩小界面字号（Ctrl+0 还原）"),    ("F1", "快捷键与数据口径说明"),
    ("Ctrl+Q", "退出"),
)


class ProcessJob:
    """A CLI subprocess whose output lines are forwarded to the Tk queue."""

    def __init__(self, argv: Sequence[str], cwd: Path, env: dict[str, str],
                 post: Callable[[tuple[str, Any]], None], owner: str = ""):
        self.argv = list(argv)
        self.cwd = Path(cwd)
        self.env = env
        self.post = post
        self.owner = owner
        self.proc: subprocess.Popen[str] | None = None
        self.started_at = 0.0
        self.stopped_at = 0.0
        self.returncode: int | None = None
        self._cancelled = False

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    @property
    def elapsed(self) -> float:
        end = self.stopped_at or time.monotonic()
        return max(0.0, end - self.started_at) if self.started_at else 0.0

    def start(self) -> None:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.started_at = time.monotonic()
        self.proc = subprocess.Popen(
            self.argv, cwd=str(self.cwd), env=self.env, text=True, bufsize=1,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf-8", errors="replace",
            creationflags=flags,
        )
        threading.Thread(target=self._pump, name="velch-cli", daemon=True).start()

    def _pump(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        try:
            for line in self.proc.stdout:
                self.post(("log", line.rstrip("\r\n")))
        finally:
            self.returncode = self.proc.wait()
            self.stopped_at = time.monotonic()
            # The job itself travels with the event: routing by "whoever owns the current slot"
            # sent a cancel or a log line to the wrong screen as soon as two jobs existed.
            self.post(("exit", (self, self.returncode, self.elapsed, self._cancelled)))

    def cancel(self) -> None:
        if self.running:
            self._cancelled = True
            self.proc.terminate()  # type: ignore[union-attr]


class VelchUI:
    """The six-screen workbench window."""

    def __init__(self, root: tk.Tk, *, headless: bool = False):
        self.root = root
        self.headless = headless
        self.queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.state = "idle"
        self.status_text = "就绪"
        self.screens: dict[str, Screen] = {}
        self.current = ""
        self.context: dict[str, Path | None] = {"run": None, "case": None}
        self.process: ProcessJob | None = None
        self._job_started = 0.0
        self._job_label = ""
        self._job_handlers = {}
        self._job_seq = 0
        self._tick_job: str | None = None
        root.title("Velch 道岔动力学工作台 · v0.4")
        root.configure(background=theme.BG)
        root.report_callback_exception = self._on_callback_error
        root.minsize(int(1180 * theme.SCALE), int(720 * theme.SCALE))
        self.build_style()
        self._build_layout()
        self._bind_keys()
        self.show("cases")
        self._pump()
        self._tick()

    # -- theme -------------------------------------------------------------
    def build_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:  # pragma: no cover - only on exotic Tk builds
            pass
        base = ui_font(theme.FONT_SIZE["body"])
        style.configure(".", background=theme.BG, foreground=theme.INK,
                        fieldbackground=theme.RAISED, font=base,
                        bordercolor=theme.BORDER, darkcolor=theme.SURFACE,
                        lightcolor=theme.SURFACE, troughcolor=theme.RAISED)
        # The vista theme asks every button for at least eleven characters (``-11``).  In a CJK
        # face that is ~153 px, so a four-button row demanded 600 px and the last ones were
        # allocated 1 px — present in the widget tree, impossible to click.  A three-character
        # floor keeps the target ~34 px wide and lets the label decide the rest.
        style.configure("TButton", width=BUTTON_MIN_CHARS)
        for name, background in (("Bg.TFrame", theme.BG), ("Card.TFrame", theme.SURFACE),
                                 ("Raised.TFrame", theme.RAISED),
                                 ("Nav.TFrame", theme.BG)):
            style.configure(name, background=background)
        style.configure("TLabel", background=theme.BG, foreground=theme.INK)
        style.configure("Card.TLabel", background=theme.SURFACE, foreground=theme.INK)
        style.configure("Muted.TLabel", background=theme.SURFACE, foreground=theme.INK_MUTED)
        style.configure("Dim.TLabel", background=theme.SURFACE, foreground=theme.INK_DIM)
        style.configure("Body.TLabel", background=theme.BG, foreground=theme.INK,
                        font=ui_font(theme.FONT_SIZE["body"]))
        style.configure("Title.TLabel", background=theme.BG, foreground=theme.INK,
                        font=ui_font(theme.FONT_SIZE["title"], bold=True))
        style.configure("Subtitle.TLabel", background=theme.BG, foreground=theme.INK_MUTED,
                        font=ui_font(theme.FONT_SIZE["body"]))
        style.configure("Section.TLabel", background=theme.SURFACE, foreground=theme.ACCENT,
                        font=ui_font(theme.FONT_SIZE["body"], bold=True))
        style.configure("CardTitle.TLabel", background=theme.SURFACE, foreground=theme.INK,
                        font=ui_font(theme.FONT_SIZE["body_lg"], bold=True))
        style.configure("Mono.TLabel", background=theme.SURFACE, foreground=theme.INK_MUTED,
                        font=(theme.FONT_MONO, theme.FONT_SIZE["tiny"]))

        # buttons ---------------------------------------------------------
        for name, background, foreground in (
            ("Ghost.TButton", theme.RAISED, theme.INK),
            ("Primary.TButton", theme.ACCENT, theme.ACCENT_INK),
            ("Danger.TButton", theme.FAIL, theme.FAIL_INK),
            ("Amber.TButton", theme.AMBER, theme.FAIL_INK),
        ):
            style.configure(name, background=background, foreground=foreground,
                            bordercolor=theme.BORDER_CONTROL, focuscolor=theme.ACCENT,
                            focusthickness=theme.FOCUS_THICKNESS, padding=(theme.SPACE["3"], 5),
                            width=BUTTON_MIN_CHARS,
                            relief="flat", font=ui_font(theme.FONT_SIZE["tiny"]))
            active = theme.OVERLAY if name == "Ghost.TButton" else theme.BORDER_STRONG
            style.map(name, background=[("pressed", theme.BORDER_STRONG),
                                        ("active", active),
                                        ("disabled", theme.SURFACE)],
                      foreground=[("disabled", theme.INK_DIM)])
        style.configure("Nav.TButton", anchor="w", padding=(theme.SPACE["3"], theme.SPACE["2"]),
                        background=theme.BG, foreground=theme.INK_MUTED, borderwidth=0,
                        relief="flat", font=ui_font(theme.FONT_SIZE["body"]))
        style.map("Nav.TButton", background=[("active", theme.SURFACE)],
                  foreground=[("active", theme.INK)])
        style.configure("NavActive.TButton", anchor="w",
                        padding=(theme.SPACE["3"], theme.SPACE["2"]),
                        background=theme.SURFACE, foreground=theme.ACCENT, borderwidth=0,
                        relief="flat", font=ui_font(theme.FONT_SIZE["body"], bold=True))

        # data views ------------------------------------------------------
        style.configure("Data.Treeview", background=theme.SURFACE,
                        fieldbackground=theme.SURFACE, foreground=theme.INK,
                        bordercolor=theme.BORDER_CONTROL, borderwidth=1,
                        rowheight=theme.TREE_ROW_HEIGHT,
                        font=ui_font(theme.FONT_SIZE["tiny"]))
        style.configure("Data.Treeview.Heading", background=theme.RAISED,
                        foreground=theme.INK_MUTED, relief="flat",
                        font=ui_font(theme.FONT_SIZE["tiny"], bold=True))
        style.map("Data.Treeview", background=[("selected", theme.OVERLAY)],
                  foreground=[("selected", theme.INK)])
        style.map("Data.Treeview.Heading", background=[("active", theme.BORDER_STRONG)])

        style.configure("Field.TEntry", fieldbackground=theme.RAISED, foreground=theme.INK,
                        insertcolor=theme.INK, bordercolor=theme.BORDER_CONTROL, padding=4,
                        selectbackground=theme.ACCENT, selectforeground=theme.ACCENT_INK)
        style.map("Field.TEntry", bordercolor=[("focus", theme.ACCENT)])
        style.configure("TCombobox", fieldbackground=theme.RAISED, background=theme.RAISED,
                        foreground=theme.INK, arrowcolor=theme.INK_MUTED,
                        bordercolor=theme.BORDER_CONTROL, padding=3)
        style.map("TCombobox", fieldbackground=[("readonly", theme.RAISED)],
                  foreground=[("readonly", theme.INK)])
        style.configure("TSpinbox", fieldbackground=theme.RAISED, foreground=theme.INK,
                        arrowcolor=theme.INK_MUTED, bordercolor=theme.BORDER_CONTROL, padding=3)
        style.configure("TScale", background=theme.SURFACE, troughcolor=theme.RAISED,
                        bordercolor=theme.BORDER)
        style.configure("TCheckbutton", background=theme.SURFACE, foreground=theme.INK,
                        indicatorcolor=theme.RAISED, focuscolor=theme.ACCENT)
        style.map("TCheckbutton", background=[("active", theme.SURFACE)],
                  indicatorcolor=[("selected", theme.ACCENT)])
        style.configure("TRadiobutton", background=theme.SURFACE, foreground=theme.INK,
                        indicatorcolor=theme.RAISED, focuscolor=theme.ACCENT,
                        font=ui_font(theme.FONT_SIZE["tiny"]))
        style.map("TRadiobutton", background=[("active", theme.SURFACE)],
                  indicatorcolor=[("selected", theme.ACCENT)],
                  foreground=[("disabled", theme.INK_DIM)])
        style.configure("Vertical.TScrollbar", background=theme.RAISED,
                        troughcolor=theme.SURFACE, bordercolor=theme.SURFACE,
                        arrowcolor=theme.INK_MUTED)
        style.configure("Horizontal.TScrollbar", background=theme.RAISED,
                        troughcolor=theme.SURFACE, bordercolor=theme.SURFACE,
                        arrowcolor=theme.INK_MUTED)
        style.configure("TSeparator", background=theme.BORDER)
        self.root.option_add("*TCombobox*Listbox.background", theme.RAISED)
        self.root.option_add("*TCombobox*Listbox.foreground", theme.INK)
        self.root.option_add("*TCombobox*Listbox.selectBackground", theme.ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", theme.ACCENT_INK)
        self.root.option_add("*TCombobox*Listbox.font", base)

    # -- layout ------------------------------------------------------------
    def _build_layout(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(1, weight=1)

        rail = ttk.Frame(self.root, style="Nav.TFrame", padding=(theme.SPACE["2"], theme.SPACE["3"]))
        rail.grid(row=0, column=0, rowspan=3, sticky="nsew")
        ttk.Label(rail, text="VELCH", style="Title.TLabel",
                  font=ui_font(theme.FONT_SIZE["title"], bold=True)).pack(anchor="w",
                                                                        padx=theme.SPACE["2"])
        ttk.Label(rail, text="道岔动力学工作台", style="Subtitle.TLabel").pack(
            anchor="w", padx=theme.SPACE["2"], pady=(0, theme.SPACE["6"]))
        self.nav_buttons: dict[str, ttk.Button] = {}
        for name, label, _subtitle, shortcut in SCREENS:
            button = ttk.Button(rail, text=label, style="Nav.TButton",
                                command=lambda n=name: self.show(n))
            button.pack(fill="x", pady=1)
            button.bind("<Return>", lambda _event, n=name: self.show(n))
            self.nav_buttons[name] = button
        ttk.Label(rail, text="快捷键", style="Dim.TLabel", background=theme.BG).pack(
            anchor="w", padx=theme.SPACE["2"], pady=(theme.SPACE["8"], 0))
        for keys, what in SHORTCUTS[:5]:
            hint = ttk.Label(rail, text=f"{keys}  {what}", style="Dim.TLabel",
                             background=theme.BG, font=ui_font(theme.FONT_SIZE["micro"]),
                             justify="left")
            hint.pack(anchor="w", fill="x", padx=theme.SPACE["2"])
            # A fixed 170 px wrap guessed the rail width; at 130 % it broke "Ctrl+1 … Ctrl+7
            # 切换到第 1–7 屏" into single-character orphans.  Follow the rail instead.
            hint.bind("<Configure>", lambda event, widget=hint: widget.configure(
                wraplength=max(120, event.width - 8)))

        header = ttk.Frame(self.root, style="Bg.TFrame",
                           padding=(theme.PAD_LG, theme.SPACE["3"], theme.PAD_LG, theme.SPACE["2"]))
        header.grid(row=0, column=1, sticky="ew")
        header.columnconfigure(0, weight=1)
        self.title_label = ttk.Label(header, text="", style="Title.TLabel")
        self.title_label.grid(row=0, column=0, sticky="w")
        self.subtitle_label = ttk.Label(header, text="", style="Subtitle.TLabel")
        self.subtitle_label.grid(row=1, column=0, sticky="w")
        right = ttk.Frame(header, style="Bg.TFrame")
        right.grid(row=0, column=1, rowspan=2, sticky="e")
        self.state_chip = Chip(right, "空闲", "idle")
        self.state_chip.pack(side="right", padx=(theme.GAP, 0))
        self.backend_label = ttk.Label(right, text=f"绘图后端 {MATPLOTLIB_BACKEND}",
                                       style="Subtitle.TLabel")
        self.backend_label.pack(side="right", padx=(0, theme.GAP))

        self.body = ttk.Frame(self.root, style="Bg.TFrame")
        self.body.grid(row=1, column=1, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)

        status = ttk.Frame(self.root, style="Nav.TFrame",
                           padding=(theme.PAD_LG, theme.SPACE["1"]))
        status.grid(row=2, column=1, sticky="ew")
        status.columnconfigure(0, weight=1)
        self.status_label = ttk.Label(status, text="就绪", style="Subtitle.TLabel",
                                      background=theme.BG)
        self.status_label.grid(row=0, column=0, sticky="w")
        # 这一步回答"这版跑过什么"。放状态栏而不是某个屏里，是因为它属于整个程序；没找到报告时
        # 它会明说"未找到"，而不是留空让人以为跑过了。它必须和另外两个标签**同一行**：多加一行
        # 状态栏会夺走 ① 屏导航按钮的高度，1.3 倍字号下那四个按钮只剩 1 px（布局闸门实测）。
        self.evidence_label = ttk.Label(status, text="", style="Dim.TLabel",
                                        background=theme.BG,
                                        font=ui_font(theme.FONT_SIZE["micro"]))
        self.evidence_label.grid(row=0, column=1, sticky="w", padx=(theme.GAP, theme.GAP))
        self.progress = ttk.Progressbar(status, mode="indeterminate", length=140,
                                        style="TProgressbar")
        self.progress.grid(row=0, column=2, sticky="e", padx=(0, theme.GAP))
        self.progress.grid_remove()
        self.context_label = ttk.Label(status, text="", style="Dim.TLabel",
                                       background=theme.BG,
                                       font=ui_font(theme.FONT_SIZE["micro"]))
        self.context_label.grid(row=0, column=3, sticky="e")

    # -- keyboard ----------------------------------------------------------
    def _bind_keys(self) -> None:
        for index, (name, *_rest) in enumerate(SCREENS, start=1):
            self.root.bind_all(f"<Control-Key-{index}>", lambda _e, n=name: self.show(n))
        self.root.bind_all("<F5>", lambda _e: self.reload_current())
        self.root.bind_all("<Control-r>", lambda _e: self.run_current())
        self.root.bind_all("<F1>", lambda _e: self.show_help())
        self.root.bind_all("<Control-q>", lambda _e: self.quit())
        self.root.bind_all("<Control-l>", lambda _e: self.focus_filter())
        self.root.bind_all("<Escape>", lambda _e: self.cancel_job())
        self.root.bind_all("<Control-e>", lambda _e: self.export_current())
        # Text size: three keys, no preferences file to find.  Both the "=" and "+" spellings are
        # bound because whether Shift is needed depends on the keyboard layout.
        for spelling in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.root.bind_all(spelling, lambda _e: self.zoom(+theme.SCALE_STEP))
        for spelling in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.root.bind_all(spelling, lambda _e: self.zoom(-theme.SCALE_STEP))
        self.root.bind_all("<Control-Key-0>", lambda _e: self.zoom(0.0, absolute=1.0))

    # -- display scale -----------------------------------------------------
    def zoom(self, delta: float, *, absolute: float | None = None) -> None:
        """Grow or shrink the type, then rebuild the window so the new size is real.

        Tk bakes the font into each widget at creation, so changing a token afterwards only
        affects widgets built later.  Rebuilding the frame tree is the honest way to apply it:
        the alternative is a UI that claims 130 % while half of it still draws at 100 %.
        """

        target = absolute if absolute is not None else theme.SCALE + delta
        applied = theme.set_scale(target)
        if applied == getattr(self, "_scale_applied", None):
            self.set_status(f"界面字号已是 {applied:.0%}", tone="idle")
            return
        self._scale_applied = applied
        current = self.current or "cases"
        for child in list(self.root.winfo_children()):
            try:
                child.destroy()
            except tk.TclError:  # pragma: no cover - already gone
                pass
        self.screens.clear()
        self.nav_buttons.clear()
        self.current = ""
        self.build_style()
        self._build_layout()
        self.show(current)
        self.set_status(f"界面字号 {applied:.0%}（Ctrl+= 放大 · Ctrl+- 缩小 · Ctrl+0 还原）",
                        tone="pass")

    # -- navigation --------------------------------------------------------
    def _build_screen(self, name: str) -> Screen:
        module = {
            "cases": ("screen_cases", "CasesScreen"),
            "run": ("screen_run", "RunScreen"),
            "timeseries": ("screen_timeseries", "TimeSeriesScreen"),
            "spectrum": ("screen_spectrum", "SpectrumScreen"),
            "assess": ("screen_assess", "AssessScreen"),
            "compare": ("screen_compare", "CompareScreen"),
            "model3d": ("screen_model3d", "Model3DScreen"),
        }[name]
        title = next(label for key, label, *_ in SCREENS if key == name)
        try:
            module_obj = __import__(f"{__package__}.{module[0]}", fromlist=[module[1]])
            factory = getattr(module_obj, module[1])
            screen = factory(self.body, self)
        except Exception as exc:  # a broken screen must not stop the app
            screen = PlaceholderScreen(self.body, self, name=name, title=title,
                                       reason=f"该屏加载失败：{type(exc).__name__}: {exc}")
        screen.grid(row=0, column=0, sticky="nsew")
        self.screens[name] = screen
        return screen

    def show(self, name: str) -> Screen:
        if name not in self.screens:
            self._build_screen(name)
        screen = self.screens[name]
        if self.current and self.current in self.screens and self.current != name:
            self.screens[self.current].on_hide()
            self.screens[self.current].grid_remove()
        label = next(label for key, label, *_ in SCREENS if key == name)
        subtitle = next(sub for key, _l, sub, *_ in SCREENS if key == name)
        self.title_label.configure(text=f"{label} · {screen.title or label}")
        self.subtitle_label.configure(text=screen.subtitle or subtitle)
        for key, button in self.nav_buttons.items():
            button.configure(style="NavActive.TButton" if key == name else "Nav.TButton")
        screen.grid()
        screen.on_show()
        self.current = name
        self.refresh_status()
        return screen

    def reload_current(self) -> None:
        if self.current:
            self.screens[self.current].reload()

    def focus_filter(self) -> None:
        screen = self.screens.get(self.current)
        target = getattr(screen, "filter_entry", None)
        if target is not None:
            target.focus_set()

    def run_current(self) -> None:
        """Ctrl+R: start the selected case from whichever screen is in front."""

        screen = self.show("run")
        starter = getattr(screen, "start_single", None)
        if starter is None:
            self.set_status("「运行」屏不可用，无法启动算例", tone="fail")
            return
        if self.process is not None and self.process.running:
            self.set_status("已有子进程在运行，先取消再启动", tone="warn")
            return
        starter()

    def export_current(self) -> None:
        screen = self.screens.get(self.current)
        exporter = getattr(screen, "export_figure", None)
        if exporter is None:
            self.set_status("当前屏没有可导出的图")
            return
        exporter()

    # -- state / status ----------------------------------------------------
    def set_state(self, state: str) -> None:
        self.state = state if state in STATES else "idle"
        label, tone = STATES[self.state]
        self.state_chip.set(f"● {label}", tone)
        if self.state == "running":
            self.progress.grid()
            self.progress.start(18)
        else:
            self.progress.stop()
            self.progress.grid_remove()

    def set_status(self, text: str, *, tone: str | None = None) -> None:
        self.status_text = text
        colour = {"fail": theme.FAIL, "pass": theme.PASS, "warn": theme.WARN,
                  "run": theme.AMBER, None: theme.INK_MUTED}.get(tone, theme.INK_MUTED)
        self.status_label.configure(text=text, foreground=colour)

    def refresh_evidence(self) -> None:
        """读最新一份冒烟/不变量报告，缩成一句话标在状态栏上。"""

        from .evidence import latest_invariants, latest_smoke, summary_text

        try:
            text, tone = summary_text(latest_smoke(), latest_invariants())
        except Exception as error:  # 证据缺失不该让界面崩
            text, tone = f"证据：读取失败（{type(error).__name__}: {error}）", "warn"
        colour = {"fail": theme.FAIL, "pass": theme.PASS, "warn": theme.WARN}
        self.evidence_label.configure(text=text, foreground=colour.get(tone, theme.INK_MUTED))

    def refresh_status(self) -> None:
        run = self.context.get("run")
        case = self.context.get("case")
        bits = []
        if case is not None:
            bits.append(f"算例 {Path(case).name}")
        if run is not None:
            bits.append(f"运行 {Path(run).name}")
        self.context_label.configure(text=" · ".join(bits) if bits else "未选择运行目录")
        self.refresh_evidence()

    def set_context(self, *, run: Path | None = None, case: Path | None = None) -> None:
        if run is not None:
            self.context["run"] = Path(run)
        if case is not None:
            self.context["case"] = Path(case)
        for screen in self.screens.values():
            handler = getattr(screen, "on_context", None)
            if handler is not None:
                try:
                    handler()
                except Exception:  # a screen must not break the others
                    pass
        self.refresh_status()

    # -- background work ---------------------------------------------------
    def spawn(self, argv: Sequence[str], cwd: Path, *, env: dict[str, str] | None = None,
              owner: str = "") -> ProcessJob | None:
        """Start a CLI subprocess; its lines arrive as ``("log", line)`` on the queue.

        Only one subprocess at a time: two would share the single ``self.process`` slot, so the
        first job's exit code went unread and ``cancel`` could terminate the other one.  Returning
        ``None`` when busy lets a caller say so instead of silently doing nothing.
        """

        if self.process is not None and self.process.running:
            self.set_status("已有子进程在运行：先取消或等它结束", tone="warn")
            return None
        job = ProcessJob(argv, cwd, env or self.cli_env(), self.queue.put, owner=owner)
        self.process = job
        job.start()
        return job

    def cli_env(self) -> dict[str, str]:
        env = dict(os.environ)
        source = str(Path(__file__).resolve().parents[2])
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = source + (os.pathsep + existing if existing else "")
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        if not self.headless:
            env.setdefault("MPLBACKEND", "Agg")
        return env

    def submit(self, label: str, work: Callable[[], Any],
               done: Callable[[bool, Any], None]) -> None:
        """Run ``work`` off the UI thread and hand the result back on the Tk thread."""

        # One slot per job, not one slot total.  With a single shared callback a second submit
        # (any screen refresh also submits) overwrote the first handler, and whichever job
        # finished first delivered its payload to the *other* handler — that is how the spectrum
        # screen ended up raising ``AttributeError: 'Series' object has no attribute 'column'``
        # and then showing nothing while the KPI cards kept the previous run's numbers.
        self._job_seq += 1
        job_id = self._job_seq

        def runner() -> None:
            try:
                result = work()
                self.queue.put(("job", (job_id, label, True, result, None)))
            except Exception as exc:  # reported, never raised into the loop
                self.queue.put(("job", (job_id, label, False, None,
                                        f"{type(exc).__name__}: {exc}")))

        self._job_handlers[job_id] = done
        self._job_label = label
        self._job_started = time.monotonic()
        self.set_state("running")
        self.set_status(f"{label} …", tone="run")
        threading.Thread(target=runner, name=f"velch-{label}", daemon=True).start()

    def cancel_job(self) -> None:
        if self.process is not None and self.process.running:
            self.process.cancel()
            self.set_status("已请求取消子进程", tone="warn")

    def _pump(self) -> None:
        """Drain the queue; one bad event must not stop the pump.

        The loop used to be ``while True: dispatch(...)`` inside ``try: ... except queue.Empty``
        with ``after(100, self._pump)`` *after* the try block.  Any handler that raised therefore
        escaped before the re-arm line: polling stopped for good, so logs froze, worker results
        were never delivered, the busy state never cleared (the run buttons stayed grey) and the
        subprocess kept going with nobody listening.  The only trace was a traceback on stderr.
        """

        try:
            while True:
                kind, payload = self.queue.get_nowait()
                try:
                    self.dispatch(kind, payload)
                except Exception as exc:  # a single event fails, the pump survives
                    traceback.print_exc()
                    self.report_problem(f"界面事件处理失败：{type(exc).__name__}: {exc}")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._pump)

    def report_problem(self, message: str) -> None:
        """Surface an internal failure where the reader can see it, not only on stderr."""

        try:
            self.set_status(message, tone="fail")
        except Exception:  # pragma: no cover - status bar itself broken
            pass

    def _on_callback_error(self, exc_type, exc_value, exc_traceback) -> None:
        """Tk swallows callback exceptions into stderr; route them to the status bar too."""

        traceback.print_exception(exc_type, exc_value, exc_traceback)
        self.report_problem(f"界面回调异常：{exc_type.__name__}: {exc_value}")

    def dispatch(self, kind: str, payload: Any) -> None:
        """Route a queue event; screens may override ``handle_event`` for their own kinds."""

        if kind == "log":
            self.on_log(str(payload))
            return
        if kind == "exit":
            self.on_exit(*payload)
            return
        if kind == "job":
            job_id, label, ok, result, error = payload
            self.set_state("done" if ok else "failed")
            handler = self._job_handlers.pop(job_id, None)
            if handler is not None:
                handler(ok, result, error)
            return
        if kind == "status":
            text, tone = payload
            self.set_status(text, tone=tone)
            return
        screen = self.screens.get(self.current)
        handler = getattr(screen, "handle_event", None)
        if handler is not None:
            handler(kind, payload)

    # per-job callbacks: one slot each, keyed by the id carried through the queue
    _job_handlers: dict[int, Callable[[bool, Any, str | None], None]] = {}
    _job_seq: int = 0

    def on_log(self, line: str, job: ProcessJob | None = None) -> None:
        screen = self._owner_screen(job)
        handler = getattr(screen, "on_log", None)
        if handler is not None:
            handler(line)

    def _owner_screen(self, job: ProcessJob | None = None) -> Screen | None:
        """The screen that owns this job; falls back to the visible one for keyboard paths."""

        owner = job.owner if job is not None else (self.process.owner if self.process else "")
        if owner and owner in self.screens:
            return self.screens[owner]
        return self.screens.get(self.current)

    def on_exit(self, job: ProcessJob | int | None = None, code: int = 0, elapsed: float = 0.0,
                cancelled: bool = False) -> None:
        """Handle a subprocess exit, routed by the job that actually exited.

        Older call sites passed ``(code, elapsed, cancelled)``; accept that shape too so a stale
        queue entry cannot raise inside the pump.
        """

        if isinstance(job, int):
            job, code, elapsed, cancelled = None, job, int(code), bool(elapsed)
        if job is not None and job is self.process:
            self.process = None
        self.set_state("done" if code == 0 else ("idle" if cancelled else "failed"))
        hint = "已取消" if cancelled else ("完成" if code == 0 else f"失败（退出码 {code}）")
        self.set_status(f"子进程{hint} · 用时 {elapsed:.1f} s",
                        tone="pass" if code == 0 else ("warn" if cancelled else "fail"))
        screen = self._owner_screen(job)
        handler = getattr(screen, "on_process_exit", None)
        if handler is not None:
            handler(code, elapsed, cancelled)

    def _tick(self) -> None:
        if self.state == "running":
            if self.process is not None and self.process.running:
                self.set_status(f"{self._job_label or 'CLI'} 运行中 · 已用 "
                                f"{self.process.elapsed:5.1f} s", tone="run")
        self._tick_job = self.root.after(300, self._tick)

    # -- misc --------------------------------------------------------------
    def show_help(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Velch 工作台 · 快捷键与数据口径")
        window.configure(background=theme.SURFACE)
        frame = ttk.Frame(window, style="Card.TFrame", padding=theme.PAD_LG)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="快捷键", style="CardTitle.TLabel").pack(anchor="w")
        for keys, what in SHORTCUTS:
            row = ttk.Frame(frame, style="Card.TFrame")
            row.pack(fill="x", pady=1)
            tk.Label(row, text=keys, width=16, anchor="w", bg=theme.SURFACE,
                     fg=theme.ACCENT, font=(theme.FONT_MONO, theme.FONT_SIZE["tiny"])
                     ).pack(side="left")
            ttk.Label(row, text=what, style="Card.TLabel").pack(side="left")
        ttk.Label(frame, text="数据口径", style="CardTitle.TLabel").pack(
            anchor="w", pady=(theme.PAD, theme.SPACE["1"]))
        for line in (
            "本界面只读运行产物与算例 JSON，只通过 CLI 子进程启动求解，不改任何数值代码。",
            "时程通道直接来自 history.csv 的列名；单位由列名后缀推断（_n → N，_m → m）。",
            "频谱调用 velch.inverse.bands 的 third_octave_levels / band_metrics，界面不做二次滤波。",
            "评价屏复用 velch assess 的同一公开函数 metrics.assess_history，读数与 CLI 一致。",
            "对照屏两侧共用同一里程轴与同一通道定义；非同一道岔时只作口径对照。",
        ):
            ttk.Label(frame, text="· " + line, style="Muted.TLabel", wraplength=720,
                      justify="left").pack(anchor="w", pady=1)
        ttk.Button(frame, text="关闭", style="Ghost.TButton",
                   command=window.destroy).pack(anchor="e", pady=(theme.PAD, 0))
        window.transient(self.root)
        window.focus_set()

    def quit(self) -> None:
        if self.process is not None and self.process.running:
            self.process.cancel()
        try:
            self.root.destroy()
        except tk.TclError:  # pragma: no cover - already gone
            pass


def build_app(headless: bool = False, *, scale: float | None = None) -> tuple[tk.Tk, VelchUI]:
    """Create the Tk root and the window; raises ``tk.TclError`` when Tk is unusable."""

    if scale is not None:
        theme.set_scale(scale)
    else:
        theme.scale_from_environment()
    root = tk.Tk()
    if headless:
        root.withdraw()
    else:
        # A bigger type needs a bigger window, but never one the screen cannot show: at 160 % a
        # 1360 px window would be 2176 px wide, which is simply off the monitor.
        width, height = int(1360 * theme.SCALE), int(860 * theme.SCALE)
        screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{min(width, screen_w - 80)}x{min(height, screen_h - 120)}")
    app = VelchUI(root, headless=headless)
    app._scale_applied = theme.SCALE
    return root, app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -X utf8 -m velch.ui",
        description="Velch 道岔动力学工作台（七屏）")
    parser.add_argument("--selftest", action="store_true",
                        help="无头自检：构造窗口、逐屏加载数据、打印统计后退出")
    parser.add_argument("--json", action="store_true", help="自检结果以 JSON 输出")
    parser.add_argument("--screens", default="",
                        help="只自检指定屏，逗号分隔（1-7 或屏名）")
    parser.add_argument("--timeout", type=float, default=180.0,
                        help="自检总超时秒数（默认 180）")
    parser.add_argument("--scale", type=float, default=None,
                        help="界面字号缩放 0.9–1.6（默认取环境变量 VELCH_UI_SCALE，否则 1.0）；"
                             "窗口里也可用 Ctrl+= / Ctrl+- / Ctrl+0")
    args = parser.parse_args(argv)

    if args.selftest or args.json:
        if args.scale is not None:
            theme.set_scale(args.scale)
        else:
            theme.scale_from_environment()
        from . import selftest
        return selftest.run(screens=args.screens, as_json=args.json,
                            timeout=args.timeout)

    try:
        root, app = build_app(headless=False, scale=args.scale)
    except tk.TclError as exc:
        print(f"[velch.ui] 无法创建 Tk 窗口：{exc}", file=sys.stderr)
        print("[velch.ui] 该环境没有可用显示；请使用 --selftest 做无头自检。",
              file=sys.stderr)
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
