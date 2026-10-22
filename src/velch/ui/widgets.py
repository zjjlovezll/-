"""Reusable widgets for the Velch UI, styled from :mod:`velch.ui.theme`.

Two constraints drive the design here:

* Matplotlib is optional.  :class:`Chart` prefers an embedded Matplotlib figure because
  the 1/3-octave bars and 2 000-point force traces are worth real axes, but when
  Matplotlib is missing it falls back to a hand-drawn :class:`tkinter.Canvas` that
  supports the same API (multi-series lines, bars, zoom, pan, reset).  Nothing else in
  the package may import Matplotlib.
* Every interactive control is a real Tk widget, so ``--selftest`` can count them and a
  screen-reader-less Windows box can still drive the whole app from the keyboard.
"""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk
from typing import Callable, Sequence

from . import theme
from .fmt import fmt_number, fmt_pair, fmt_percent

try:  # optional: only the chart needs it
    import warnings

    from matplotlib import rcParams
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    # CJK labels are part of the UI copy, so the axes need a font that has them.  This is
    # global Matplotlib state, set once here rather than per figure.
    rcParams["font.sans-serif"] = [theme.FONT_UI, "Microsoft YaHei", "SimHei",
                                   "DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False
    warnings.filterwarnings("ignore", message=".*missing from font.*")
    warnings.filterwarnings("ignore", message="Glyph .* missing from font.*")
    MATPLOTLIB_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only on a box without Matplotlib
    FigureCanvasTkAgg = None  # type: ignore[assignment]
    Figure = None  # type: ignore[assignment]
    MATPLOTLIB_AVAILABLE = False

MATPLOTLIB_BACKEND = "matplotlib" if MATPLOTLIB_AVAILABLE else "tk-canvas"


# ---------------------------------------------------------------------------
# structure
# ---------------------------------------------------------------------------

def ui_font(size: int = theme.FONT_SIZE["body"], *, bold: bool = False) -> tuple:
    return (theme.FONT_UI, size, "bold") if bold else (theme.FONT_UI, size)


def mono_font(size: int = theme.FONT_SIZE["micro"]) -> tuple:
    return (theme.FONT_MONO, size)


class Card(ttk.Frame):
    """A raised panel with an optional title strip."""

    def __init__(self, parent: tk.Misc, title: str = "", *, padding: int = theme.PAD,
                 tone: str = theme.SURFACE):
        super().__init__(parent, style="Card.TFrame", padding=padding)
        self.tone = tone
        if title:
            header = ttk.Frame(self, style="Card.TFrame")
            header.pack(fill="x", pady=(0, theme.GAP))
            ttk.Label(header, text=title, style="CardTitle.TLabel").pack(side="left")

    def body(self) -> ttk.Frame:
        frame = ttk.Frame(self, style="Card.TFrame")
        frame.pack(fill="both", expand=True)
        return frame


class Chip(tk.Label):
    """Status pill: ``tone`` picks the palette entry from :mod:`velch.ui.theme`."""

    TONES = {
        "pass": (theme.PASS, theme.PASS_INK),
        "fail": (theme.FAIL, theme.FAIL_INK),
        "warn": (theme.WARN, theme.FAIL_INK),
        "idle": (theme.RAISED, theme.INK_MUTED),
        "run": (theme.AMBER, theme.FAIL_INK),
        "info": (theme.INFO, theme.ACCENT_INK),
        "accent": (theme.ACCENT, theme.ACCENT_INK),
    }

    def __init__(self, parent: tk.Misc, text: str = "", tone: str = "idle"):
        super().__init__(parent, text=text, padx=theme.GAP, pady=1,
                         font=ui_font(theme.FONT_SIZE["micro"], bold=True),
                         bd=0, highlightthickness=0)
        self.set(text, tone)

    def set(self, text: str, tone: str | None = None) -> None:
        if tone is not None:
            background, foreground = self.TONES.get(tone, self.TONES["idle"])
            self.configure(background=background, foreground=foreground)
        self.configure(text=text)


class MetricCard(ttk.Frame):
    """Label / big numeral / unit, the atom of the assessment and run screens."""

    def __init__(self, parent: tk.Misc, label: str, value: str = "—", unit: str = "",
                 *, tone: str = theme.INK, width: int = 16):
        super().__init__(parent, style="Raised.TFrame", padding=(theme.SPACE["3"], theme.SPACE["2"]))
        self.label = ttk.Label(self, text=label, style="Muted.TLabel",
                               font=ui_font(theme.FONT_SIZE["micro"]))
        self.label.pack(anchor="w")
        row = ttk.Frame(self, style="Raised.TFrame")
        row.pack(anchor="w", fill="x")
        self.value = tk.Label(row, text=value, fg=tone, bg=theme.RAISED,
                              font=mono_font(theme.FONT_SIZE["section"]), anchor="w")
        self.value.pack(side="left")
        self.unit = tk.Label(row, text=unit, fg=theme.INK_DIM, bg=theme.RAISED,
                             font=ui_font(theme.FONT_SIZE["micro"]))
        self.unit.pack(side="left", padx=(3, 0), pady=(4, 0))
        self.configure(width=width)

    def set(self, value: str, unit: str | None = None, tone: str | None = None) -> None:
        self.value.configure(text=value)
        if unit is not None:
            self.unit.configure(text=unit)
        if tone is not None:
            self.value.configure(fg=tone)


class LimitBar(tk.Canvas):
    """``value`` against ``limit`` as a filled bar with a hard limit marker."""

    def __init__(self, parent: tk.Misc, label: str, *, caption: str = "",
                 height: int = 64, unit: str = ""):
        # ``width=1`` keeps the canvas from demanding its default 378 px: the bar's width is
        # whatever the card gives it.  Without this the reading was laid out past the card edge
        # and "3896 / 4.979e+04" arrived on screen as "3896 / 4.97" — off by four orders of
        # magnitude, in an engineering verdict.
        super().__init__(parent, height=int(height * theme.SCALE), width=1, bg=theme.SURFACE,
                         highlightthickness=0, bd=0)
        self._label = label
        self._caption = caption
        self._unit = unit
        self._value = 0.0
        self._limit = 1.0
        self._passed = True
        self.bind("<Configure>", lambda _event: self._draw())

    def set(self, value: float, limit: float, passed: bool, caption: str | None = None) -> None:
        self._value, self._limit, self._passed = value, limit, passed
        if caption is not None:
            self._caption = caption
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        if width <= 1:            # not mapped yet: <Configure> will call us again
            return
        left, right = 0, width - 2
        top = int(26 * theme.SCALE)
        track_h = int(10 * theme.SCALE)
        if not (math.isfinite(self._value) and math.isfinite(self._limit)):
            # NaN compares False against everything, so a missing value used to fall through to
            # the "pass" colour: a bar with no data read as a bar that satisfied the limit.
            self.create_text(left, 0, text=self._label, anchor="nw", fill=theme.INK,
                             font=ui_font(theme.FONT_SIZE["tiny"]))
            self.create_text(right, 0, text="—", anchor="ne", fill=theme.INK_MUTED,
                             font=mono_font(theme.FONT_SIZE["tiny"]))
            self.create_rectangle(left, top, right, top + track_h, fill=theme.RAISED, outline="")
            self.create_text(left, top + track_h + int(6 * theme.SCALE), text="无有效值",
                             anchor="nw", fill=theme.INK_MUTED,
                             font=ui_font(theme.FONT_SIZE["micro"]))
            return
        ratio = 0.0 if self._limit <= 0 else min(self._value / self._limit, 1.35)
        if not self._passed or ratio >= 1.0:
            colour = theme.FAIL
        elif ratio >= 0.8:
            colour = theme.WARN
        else:
            colour = theme.PASS
        self.create_text(left, 0, text=self._label, anchor="nw", fill=theme.INK,
                         font=ui_font(theme.FONT_SIZE["tiny"]))
        reading = fmt_pair(self._value, self._limit, self._unit)
        self.create_text(right, 0, text=reading, anchor="ne", fill=colour,
                         font=mono_font(theme.FONT_SIZE["tiny"]))
        self.create_rectangle(left, top, right, top + track_h, fill=theme.RAISED, outline="")
        span = right - left
        warn_x = left + span * 0.8
        self.create_line(warn_x, top - 2, warn_x, top + track_h + 2,
                         fill=theme.WARN, width=1, dash=(2, 2))
        bar_right = left + span * min(ratio, 1.0)
        self.create_rectangle(left, top, max(bar_right, left + 1), top + track_h,
                              fill=colour, outline="")
        self.create_line(right, top - 3, right, top + track_h + 3, fill=theme.FAIL, width=2)
        detail = fmt_percent(ratio) + ("  超限" if ratio >= 1.0 else "")
        if self._caption:
            detail = f"{detail} · {self._caption}"
        self.create_text(left, top + track_h + int(6 * theme.SCALE), text=detail, anchor="nw",
                         fill=theme.INK_MUTED, font=ui_font(theme.FONT_SIZE["micro"]))


class GateList(ttk.Frame):
    """The seven manifest gates as rows: status chip, Chinese label, recorded value."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent, style="Card.TFrame")
        self.rows: list[ttk.Frame] = []
        self._grid: dict[str, tuple[Chip, ttk.Label, ttk.Label]] = {}

    def build(self, entries: Sequence[tuple[str, str, str]]) -> None:
        """``entries`` = ``(key, label, detail_text)``; rebuilds when the key set changes."""

        for child in self.winfo_children():
            child.destroy()
        self.rows.clear()
        self._grid.clear()
        for index, (key, label, detail) in enumerate(entries):
            row = ttk.Frame(self, style="Card.TFrame")
            row.pack(fill="x", pady=(0 if index == 0 else 3, 0))
            chip = Chip(row, "待运行", "idle")
            chip.pack(side="left")
            text = ttk.Label(row, text=label, style="Card.TLabel",
                             font=ui_font(theme.FONT_SIZE["tiny"]))
            text.pack(side="left", padx=(theme.GAP, 0))
            note = ttk.Label(row, text=detail, style="Dim.TLabel",
                             font=mono_font(theme.FONT_SIZE["micro"]))
            note.pack(side="right")
            self.rows.append(row)
            self._grid[key] = (chip, text, note)

    def set(self, key: str, passed: bool | None, detail: str = "") -> None:
        entry = self._grid.get(key)
        if entry is None:
            return
        chip, _text, note = entry
        if passed is None:
            chip.set("待运行", "idle")
        else:
            chip.set("通过" if passed else "失败", "pass" if passed else "fail")
        note.configure(text=detail)


class ListPanel(ttk.Frame):
    """Labelled list of selectable text items with scrollbars (filterable)."""

    def __init__(self, parent: tk.Misc, *, height: int = 12, selectmode: str = "browse",
                 mono: bool = False):
        super().__init__(parent, style="Card.TFrame")
        self.tree = ttk.Treeview(self, show="headings", selectmode=selectmode, height=height,
                                 style="Data.Treeview")
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        # A table whose columns are declared wider than its panel is not "slightly clipped" —
        # the last column simply cannot be read, and on the cases screen that column is the file
        # hash.  The horizontal bar is cheap; guessing a width that always fits is not.
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._scroll = vertical
        self._scroll_x = horizontal
        self._mono = mono

    def columns(self, spec: Sequence[tuple[str, str, int]], *, anchor: str = "w",
                stretch_weights: Sequence[float] | None = None) -> None:
        ids = [name for name, _title, _width in spec]
        self.tree.configure(columns=ids)
        weights = list(stretch_weights or [1.0] * len(ids))
        for index, (name, title, width) in enumerate(spec):
            self.tree.heading(name, text=title, anchor=anchor)
            # Column widths are declared at the 100 % scale; the type inside them is not.  Without
            # this the header grows past its column and the last cell is cut off — the exact
            # failure mode that made 130 % look broken.
            self.tree.column(name, width=int(width * theme.SCALE), anchor=anchor,
                             minwidth=int(width * 0.7 * theme.SCALE),
                             stretch=weights[index] > 0)

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())


# ---------------------------------------------------------------------------
# chart
# ---------------------------------------------------------------------------

class ChartSeries:
    """One drawn series: ``kind`` is ``line`` or ``bar``."""

    __slots__ = ("label", "xs", "ys", "color", "kind", "width", "filled")

    def __init__(self, label: str, xs: Sequence[float], ys: Sequence[float],
                 color: str = theme.ACCENT, kind: str = "line", width: float = 1.6,
                 filled: bool = False):
        self.label = label
        self.xs = xs
        self.ys = ys
        self.color = color
        self.kind = kind
        self.width = width
        self.filled = filled


class Chart(ttk.Frame):
    """Line/bar plot with wheel-zoom, drag-pan and double-click reset.

    Matplotlib is used when importable; otherwise the same public API is served by a
    hand-drawn Tk canvas (the fallback required by the project constraints).
    """

    def __init__(self, parent: tk.Misc, *, height: int = 260, ylabel: str = "",
                 xlabel: str = "", zoomable: bool = True, empty_hint: str = "选择数据以绘图"):
        super().__init__(parent, style="Card.TFrame")
        self.height = height
        self.ylabel = ylabel
        self.xlabel = xlabel
        self.zoomable = zoomable
        self.empty_hint = empty_hint
        self.series: list[ChartSeries] = []
        self.x_window: tuple[float, float] | None = None
        self.y_window: tuple[float, float] | None = None
        self.x_ticks: list[tuple[float, str]] | None = None
        self.reference_lines: list[tuple[float, float, str, str]] = []
        self._drag: tuple[float, float] | None = None
        self._canvas: tk.Canvas | None = None
        self._figure = None
        self._axes = None
        self.backend = MATPLOTLIB_BACKEND
        if MATPLOTLIB_AVAILABLE:
            self._build_matplotlib()
        else:
            self._build_canvas()

    # -- construction ------------------------------------------------------
    def _build_matplotlib(self) -> None:
        figure = Figure(figsize=(6.0, self.height / 96.0), dpi=96, facecolor=theme.SURFACE)
        axes = figure.add_subplot(111)
        widget = FigureCanvasTkAgg(figure, master=self)
        widget.get_tk_widget().configure(bg=theme.SURFACE, highlightthickness=0)
        widget.get_tk_widget().pack(fill="both", expand=True)
        widget.draw()
        self._figure, self._axes = figure, axes
        self._mpl_widget = widget
        self._pixel_size: tuple[int, int] = (0, 0)
        self.bind("<Configure>", self._on_configure)
        if self.zoomable:
            widget.mpl_connect("scroll_event", self._on_scroll_mpl)
            widget.mpl_connect("button_press_event", self._on_press_mpl)
            widget.mpl_connect("motion_notify_event", self._on_motion_mpl)
            widget.mpl_connect("button_release_event", self._on_release_mpl)

    def _on_configure(self, event: tk.Event) -> None:
        """Keep the Matplotlib canvas at the real widget size so charts fill the card."""

        width = max(int(event.width), 160)
        height = max(int(event.height), 90)
        if abs(width - self._pixel_size[0]) < 8 and abs(height - self._pixel_size[1]) < 8:
            return
        self._pixel_size = (width, height)
        dpi = self._figure.dpi
        self._figure.set_size_inches(width / dpi, height / dpi)
        self._render()

    def _build_canvas(self) -> None:
        canvas = tk.Canvas(self, bg=theme.SURFACE, highlightthickness=0, bd=0,
                           height=self.height)
        canvas.pack(fill="both", expand=True)
        canvas.bind("<Configure>", lambda _event: self._draw_canvas())
        if self.zoomable:
            canvas.bind("<MouseWheel>", self._on_wheel_tk)
            canvas.bind("<ButtonPress-1>", self._on_press_tk)
            canvas.bind("<B1-Motion>", self._on_motion_tk)
            canvas.bind("<ButtonRelease-1>", self._on_release_tk)
            canvas.bind("<Double-Button-1>", lambda _event: self.reset_view())
        self._canvas = canvas

    # -- public API --------------------------------------------------------
    def set_series(self, series: Sequence[ChartSeries], *, ylabel: str | None = None,
                   xlabel: str | None = None,
                   reference_lines: Sequence[tuple[float, float, str, str]] = (),
                   x_ticks: Sequence[tuple[float, str]] | None = None) -> None:
        self.series = list(series)
        self.reference_lines = list(reference_lines)
        self.x_ticks = list(x_ticks) if x_ticks else None
        if ylabel is not None:
            self.ylabel = ylabel
        if xlabel is not None:
            self.xlabel = xlabel
        self.y_window = None
        self._render()

    def clear(self) -> None:
        self.series = []
        self.reference_lines = []
        self.x_ticks = None
        self.x_window = None
        self.y_window = None
        self._render()

    def reset_view(self) -> None:
        self.x_window = None
        self.y_window = None
        self._render()

    def export_png(self, path) -> bool:
        """Write the current figure through Matplotlib; no-op on the canvas backend."""

        if self._figure is None:
            return False
        self._figure.savefig(path, facecolor=theme.SURFACE, dpi=144)
        return True

    # -- range helpers -----------------------------------------------------
    def _x_bounds(self) -> tuple[float, float]:
        if self.x_window is not None:
            return self.x_window
        xs = [v for s in self.series for v in s.xs]
        if not xs:
            return 0.0, 1.0
        low, high = min(xs), max(xs)
        return (low, high) if high > low else (low, low + 1.0)

    def _is_bar_chart(self) -> bool:
        return bool(self.series) and all(s.kind == "bar" for s in self.series)

    # -- rendering ---------------------------------------------------------
    def _render(self) -> None:
        if self._axes is not None:
            self._draw_matplotlib()
        elif self._canvas is not None:
            self._draw_canvas()

    def _draw_matplotlib(self) -> None:
        axes = self._axes
        figure = self._figure
        axes.clear()
        axes.set_facecolor(theme.SURFACE)
        for spine in axes.spines.values():
            spine.set_color(theme.BORDER)
        axes.tick_params(colors=theme.INK_MUTED, labelsize=theme.FONT_SIZE["micro"])
        axes.grid(True, color=theme.RAISED, linewidth=0.8, zorder=0)
        axes.set_xlabel(self.xlabel, color=theme.INK_MUTED, fontsize=theme.FONT_SIZE["micro"])
        axes.set_ylabel(self.ylabel, color=theme.INK_MUTED, fontsize=theme.FONT_SIZE["micro"])
        if not self.series:
            axes.text(0.5, 0.5, self.empty_hint, color=theme.INK_DIM, ha="center",
                      va="center", transform=axes.transAxes, fontsize=theme.FONT_SIZE["body"])
            axes.set_xticks([])
            axes.set_yticks([])
            figure.tight_layout(pad=0.6)
            self._mpl_widget.draw_idle()
            return
        low, high = self._x_bounds()
        if self._is_bar_chart():
            first = self.series[0]
            axes.bar(first.xs, first.ys, width=self._bar_width(first.xs),
                     color=first.color, zorder=3)
        else:
            for line in self.series:
                xs, ys = self._clip(line.xs, line.ys, low, high)
                if len(xs) == 0:
                    continue
                axes.plot(xs, ys, color=line.color, linewidth=line.width, label=line.label,
                          zorder=3)
        for value, _unused, label, colour in self.reference_lines:
            axes.axhline(value, color=colour, linewidth=1.0, linestyle="--", zorder=2)
            if label:
                axes.annotate(label, xy=(0.995, value), xycoords=("axes fraction", "data"),
                              ha="right", va="bottom", color=colour,
                              fontsize=theme.FONT_SIZE["micro"])
        axes.set_xlim(low, high)
        if self.x_ticks:
            axes.set_xticks([pos for pos, _label in self.x_ticks],
                            [label for _pos, label in self.x_ticks])
            axes.tick_params(axis="x", labelsize=theme.FONT_SIZE["micro"] - 1, labelrotation=90)
        if self.y_window is not None:
            axes.set_ylim(*self.y_window)
        named = [line for line in self.series if line.label]
        if named and not self._is_bar_chart():
            # One series still needs its name: on the time-history screen three curves share a
            # window, and without a legend nothing said which axle and which rail each one was.
            legend = axes.legend(loc="upper right", fontsize=theme.FONT_SIZE["micro"],
                                 facecolor=theme.OVERLAY, edgecolor=theme.BORDER)
            for text in legend.get_texts():
                text.set_color(theme.INK)
        self._compact_ticks(axes)
        figure.tight_layout(pad=0.6)
        self._mpl_widget.draw_idle()

    def _compact_ticks(self, axes) -> None:
        """Four significant digits per tick, with an explicit exponent only when it is needed.

        Matplotlib's defaults fail on both ends of this data: a force that barely moves gets
        ``1e-17+5.96e4`` (an offset label nobody can read), and the same force with the offset
        disabled gets ``59680.5768588`` (twelve digits of noise).  Four significant figures is
        what the physics justifies, and ``%.2e`` keeps extreme magnitudes short.
        """

        from matplotlib.ticker import FuncFormatter

        def text(value: float, _position: float) -> str:
            if value == 0:
                return "0"
            magnitude = abs(value)
            if 1e-3 <= magnitude < 1e4:
                return fmt_number(value)
            return f"{value:.2e}".replace("e+0", "e+").replace("e-0", "e-")

        formatter = FuncFormatter(text)
        if not self.x_ticks:
            # An explicit tick label (a band frequency, a station) is the caller's decision and
            # must survive: replacing its formatter would print the log position instead of the
            # frequency the caller asked for.
            axes.xaxis.set_major_formatter(formatter)
        axes.yaxis.set_major_formatter(formatter)

    @staticmethod
    def _bar_width(xs: Sequence[float]) -> float:
        if len(xs) < 2:
            return 0.6
        return float(min(abs(xs[1] - xs[0]), abs(xs[-1] - xs[0]) / max(len(xs) - 1, 1))) * 0.7

    @staticmethod
    def _clip(xs: Sequence[float], ys: Sequence[float], low: float, high: float):
        pairs = [(x, y) for x, y in zip(xs, ys) if low <= x <= high]
        if not pairs:
            return [], []
        return [p[0] for p in pairs], [p[1] for p in pairs]

    def _draw_canvas(self) -> None:
        canvas = self._canvas
        if canvas is None:
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), self.height)
        left, right, top, bottom = 74, width - 22, 26, height - 46
        canvas.create_rectangle(left, top, right, bottom, outline=theme.BORDER)
        if not self.series:
            canvas.create_text(width / 2, height / 2, text=self.empty_hint,
                               fill=theme.INK_DIM, font=ui_font(theme.FONT_SIZE["body"]))
            return
        low, high = self._x_bounds()
        values = [v for line in self.series for v in line.ys]
        if not values:
            return
        if self.y_window is not None:
            v_low, v_high = self.y_window
        elif self._is_bar_chart():
            v_low, v_high = 0.0, max(values) * 1.08 or 1.0
        else:
            v_low, v_high = min(values), max(values)
            if v_high == v_low:
                v_low, v_high = v_low - 1.0, v_high + 1.0
            pad = (v_high - v_low) * 0.08
            v_low, v_high = v_low - pad, v_high + pad
        for index in range(5):
            xx = left + (right - left) * index / 4
            yy = bottom - (bottom - top) * index / 4
            canvas.create_line(xx, top, xx, bottom, fill=theme.RAISED)
            canvas.create_line(left, yy, right, yy, fill=theme.RAISED)
            canvas.create_text(xx, bottom + 14,
                                text=fmt_number(low + (high - low) * index / 4),
                               fill=theme.INK_DIM, font=mono_font())
            canvas.create_text(left - 8, yy,
                                text=fmt_number(v_low + (v_high - v_low) * index / 4),
                               fill=theme.INK_DIM, anchor="e", font=mono_font())
        if self.x_ticks:  # bar charts label each band instead of the 4-way split
            for pos, label in self.x_ticks:
                if not (low <= pos <= high):
                    continue
                xx = left + (pos - low) / ((high - low) or 1.0) * (right - left)
                canvas.create_line(xx, bottom, xx, bottom + 3, fill=theme.BORDER)
                canvas.create_text(xx, bottom + 14, text=label, angle=90,
                                   fill=theme.INK_DIM, font=mono_font())
        span_x = (high - low) or 1.0
        span_y = (v_high - v_low) or 1.0

        def px(x: float) -> float:
            return left + (x - low) / span_x * (right - left)

        def py(y: float) -> float:
            return bottom - (y - v_low) / span_y * (bottom - top)

        for value, _unused, label, colour in self.reference_lines:
            canvas.create_line(left, py(value), right, py(value), fill=colour, dash=(4, 3))
            if label:
                canvas.create_text(right - 4, py(value) - 8, text=label, anchor="e",
                                   fill=colour, font=mono_font())
        if self._is_bar_chart():
            first = self.series[0]
            step = (right - left) / max(len(first.xs), 1)
            for x, y in zip(first.xs, first.ys):
                x0 = px(x) - step * 0.32
                x1 = px(x) + step * 0.32
                canvas.create_rectangle(x0, py(max(y, 0.0)), x1, py(min(y, 0.0)),
                                        fill=first.color, outline="")
        else:
            for line in self.series:
                coords: list[float] = []
                for x, y in zip(line.xs, line.ys):
                    if x < low or x > high:
                        continue
                    coords.extend((px(x), py(y)))
                if len(coords) >= 4:
                    canvas.create_line(*coords, fill=line.color, width=int(line.width))
                elif coords:
                    canvas.create_oval(coords[0] - 2, coords[1] - 2, coords[0] + 2,
                                       coords[1] + 2, fill=line.color, outline="")
        canvas.create_text(left, 12, text=self.ylabel, anchor="w", fill=theme.INK_MUTED,
                           font=ui_font(theme.FONT_SIZE["micro"], bold=True))
        canvas.create_text((left + right) / 2, height - 14, text=self.xlabel,
                           fill=theme.INK_MUTED, font=ui_font(theme.FONT_SIZE["micro"]))

    # -- zoom / pan --------------------------------------------------------
    def zoom_x(self, factor: float, anchor: float | None = None) -> None:
        low, high = self._x_bounds()
        span = high - low
        if span <= 0:
            return
        centre = low + span / 2 if anchor is None else anchor
        new_span = span * factor
        new_low = centre - (centre - low) * factor
        new_high = new_low + new_span
        self.x_window = (new_low, new_high)
        self._render()

    def pan_x(self, fraction: float) -> None:
        low, high = self._x_bounds()
        shift = (high - low) * fraction
        self.x_window = (low + shift, high + shift)
        self._render()

    def _on_scroll_mpl(self, event) -> None:
        if not self.zoomable or event.inaxes is None or event.xdata is None:
            return
        self.zoom_x(0.8 if event.step > 0 else 1.25, float(event.xdata))

    def _on_press_mpl(self, event) -> None:
        if event.inaxes is not None and event.xdata is not None:
            self._drag = (float(event.xdata), float(event.xdata))

    def _on_motion_mpl(self, event) -> None:
        if self._drag is None or event.inaxes is None:
            return
        self._drag = (self._drag[0], float(event.xdata) if event.xdata is not None else self._drag[1])

    def _on_release_mpl(self, event) -> None:
        if self._drag is None:
            return
        start, end = self._drag
        self._drag = None
        low, high = self._x_bounds()
        span = high - low
        if abs(end - start) < span * 0.01:      # treat as a click
            return
        if abs(end - start) > span * 0.02:      # drag = pan, not box zoom
            shift = start - end
            self.x_window = (low + shift, high + shift)
            self._render()

    def _on_wheel_tk(self, event) -> None:
        anchor = self._tk_x(event) or None
        self.zoom_x(0.8 if event.delta > 0 else 1.25, anchor)

    def _on_press_tk(self, event) -> None:
        self._drag = (self._tk_x(event), self._tk_x(event))

    def _on_motion_tk(self, event) -> None:
        if self._drag is None:
            return
        self._drag = (self._drag[0], self._tk_x(event))

    def _on_release_tk(self, event) -> None:
        if self._drag is None:
            return
        start, end = self._drag
        self._drag = None
        low, high = self._x_bounds()
        span = (high - low) or 1.0
        if abs(end - start) < span * 0.01:
            return
        shift = start - end
        self.x_window = (low + shift, high + shift)
        self._render()

    def _tk_x(self, event) -> float:
        canvas = self._canvas
        if canvas is None:
            return 0.0
        width = max(canvas.winfo_width(), 320)
        left, right = 74, width - 22
        low, high = self._x_bounds()
        fraction = (event.x - left) / max(right - left, 1)
        return low + (high - low) * min(max(fraction, 0.0), 1.0)


def count_widgets(widget: tk.Misc) -> int:
    """Total Tk widget count in a subtree (used by --selftest)."""

    total = 1
    for child in widget.winfo_children():
        total += count_widgets(child)
    return total


def make_button(parent: tk.Misc, text: str, command: Callable[[], None], *,
                style: str = "Ghost.TButton", width: int | None = None) -> ttk.Button:
    button = ttk.Button(parent, text=text, command=command, style=style,
                        takefocus=True)
    if width:
        button.configure(width=width)
    return button


def labeled_entry(parent: tk.Misc, label: str, variable: tk.Variable, *,
                  width: int = 34, hint: str = "") -> ttk.Frame:
    frame = ttk.Frame(parent, style="Card.TFrame")
    ttk.Label(frame, text=label, style="Muted.TLabel",
              font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
    entry = ttk.Entry(frame, textvariable=variable, width=width, style="Field.TEntry")
    entry.pack(fill="x")
    if hint:
        ttk.Label(frame, text=hint, style="Dim.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w", pady=(2, 0))
    setattr(frame, "entry", entry)
    return frame
