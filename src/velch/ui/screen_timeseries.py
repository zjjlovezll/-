"""Screen ③「结果-时程」: pick channels from ``history.csv`` and plot them grouped by unit.

Channels are grouped by the unit inferred from their column suffix, and **each unit group
gets its own y axis** — a 600 kN normal force and a 0.4 mm penetration must never share a
scale.  Zoom and pan are per group and stay in sync because all groups share one x window
state held by the screen.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from . import store, theme
from .screen import Screen
from .widgets import Chart, ChartSeries, ui_font

MAX_POINTS = 2400
MAX_GROUPS = 4
PRESETS: dict[str, tuple[str, ...]] = {
    "接触力": ("axle1_right_normal_n", "axle1_left_normal_n",
              "axle2_right_normal_n", "axle2_left_normal_n"),
    "位移": ("axle1_z_m", "axle1_y_m", "carbody_z_m", "carbody_y_m"),
    "侵入量": ("axle1_right_penetration_m", "axle1_left_penetration_m"),
    "速度": ("axle1_z_m_per_s", "carbody_z_m_per_s"),
}
DEFAULT_CHANNELS = ("axle1_right_normal_n", "axle1_z_m", "axle1_right_penetration_m")


class TimeSeriesScreen(Screen):
    name = "timeseries"
    title = "时程曲线"
    subtitle = "按 history.csv 通道多选；纵轴按单位分组，各自独立标度，滚轮缩放、拖拽平移"

    def _build(self) -> None:
        self.runs: list[store.RunInfo] = []
        self.series: store.Series | None = None
        self.columns: list[str] = []
        self.groups: dict[str, list[str]] = {}
        self.charts: list[Chart] = []
        self.drawn = 0
        self.summary_var = tk.StringVar(value="未加载")
        self.max_points_var = tk.IntVar(value=MAX_POINTS)
        self.run_var = tk.StringVar()

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, style="Bg.TFrame", width=int(330 * theme.SCALE))
        left.grid(row=0, column=0, sticky="nsew", padx=(0, theme.SPACE["3"]))
        left.grid_propagate(False)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(3, weight=1)

        run_card = ttk.Frame(left, style="Raised.TFrame", padding=theme.SPACE["3"])
        run_card.grid(row=0, column=0, sticky="ew", pady=(0, theme.SPACE["2"]))
        ttk.Label(run_card, text="运行目录", style="Muted.TLabel", background=theme.RAISED,
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
        self.run_combo = ttk.Combobox(run_card, textvariable=self.run_var,
                                      state="readonly", height=18)
        self.run_combo.pack(fill="x", pady=(2, 0))
        self.run_combo.bind("<<ComboboxSelected>>", lambda _e: self.load_run())

        preset_card = ttk.Frame(left, style="Raised.TFrame", padding=theme.SPACE["3"])
        preset_card.grid(row=1, column=0, sticky="ew", pady=(0, theme.SPACE["2"]))
        ttk.Label(preset_card, text="通道预设", style="Muted.TLabel",
                  background=theme.RAISED,
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
        row = ttk.Frame(preset_card, style="Raised.TFrame")
        row.pack(fill="x", pady=(2, 0))
        for label in PRESETS:
            ttk.Button(row, text=label, style="Ghost.TButton",
                       command=lambda name=label: self.apply_preset(name)).pack(
                side="left", padx=(0, theme.SPACE["1"]))

        chan_card = ttk.Frame(left, style="Card.TFrame", padding=theme.SPACE["3"])
        chan_card.grid(row=3, column=0, sticky="nsew")
        chan_card.columnconfigure(0, weight=1)
        chan_card.rowconfigure(2, weight=1)
        ttk.Label(chan_card, text="通道（按单位分组，多选）", style="CardTitle.TLabel",
                  font=ui_font(theme.FONT_SIZE["tiny"], bold=True)).grid(row=0, column=0,
                                                                        sticky="w")
        ttk.Label(chan_card, text="Ctrl/Shift 多选；组内共享一个纵轴",
                  style="Dim.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).grid(row=1, column=0, sticky="w")
        tree_frame = ttk.Frame(chan_card, style="Card.TFrame")
        tree_frame.grid(row=2, column=0, sticky="nsew", pady=(theme.SPACE["2"], 0))
        self.channel_tree = ttk.Treeview(tree_frame, show="tree", selectmode="extended",
                                         style="Data.Treeview", height=14)
        scroll = ttk.Scrollbar(tree_frame, orient="vertical",
                               command=self.channel_tree.yview)
        self.channel_tree.configure(yscrollcommand=scroll.set)
        self.channel_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.channel_tree.bind("<<TreeviewSelect>>", lambda _e: self.draw_selected())
        self.channel_tree.tag_configure("unit", foreground=theme.ACCENT)

        info = ttk.Frame(left, style="Bg.TFrame")
        info.grid(row=4, column=0, sticky="ew", pady=(theme.SPACE["2"], 0))
        ttk.Label(info, textvariable=self.summary_var, style="Subtitle.TLabel",
                  background=theme.BG, wraplength=320, justify="left").pack(anchor="w")

        right = ttk.Frame(self, style="Bg.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(right, style="Bg.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, theme.SPACE["2"]))
        for text, command in (("重置", self.reset_zoom),
                              ("放大", lambda: self.zoom(0.7)),
                              ("缩小", lambda: self.zoom(1.4)),
                              ("←", lambda: self.pan(-0.25)),
                              ("→", lambda: self.pan(0.25)),
                              ("PNG", self.export_figure)):
            ttk.Button(toolbar, text=text, style="Ghost.TButton",
                       command=command).pack(side="left", padx=(0, theme.SPACE["1"]))
        ttk.Spinbox(toolbar, from_=200, to=20000, increment=200,
                    textvariable=self.max_points_var, width=6,
                    style="TSpinbox", command=self.draw_selected).pack(side="right")
        ttk.Label(toolbar, text="点数上限", style="Subtitle.TLabel",
                  background=theme.BG).pack(side="right", padx=(theme.GAP, theme.SPACE["1"]))

        self.chart_area = ttk.Frame(right, style="Bg.TFrame")
        self.chart_area.grid(row=1, column=0, sticky="nsew")
        self.chart_area.columnconfigure(0, weight=1)
        for index in range(MAX_GROUPS):
            self.chart_area.rowconfigure(index, weight=1)
            chart = Chart(self.chart_area, height=180, empty_hint="在左侧选择通道")
            chart.grid(row=index, column=0, sticky="nsew", pady=(0, theme.SPACE["2"]))
            if index:
                chart.grid_remove()
            self.charts.append(chart)

    # -- data --------------------------------------------------------------
    def refresh(self) -> None:
        self.runs = [run for run in store.scan_runs() if run.columns and not run.problem]
        values = [store.run_label(run) for run in self.runs]
        self.run_combo.configure(values=values)
        wanted = self.app.context.get("run")
        index = 0
        if wanted is not None:
            for position, run in enumerate(self.runs):
                if run.path == Path(wanted):
                    index = position
                    break
        if values:
            self.run_combo.current(index)
            self.load_run()
        self.set_rows(len(self.runs), f"{len(self.runs)} 个可读运行目录")

    def _current_run(self) -> store.RunInfo | None:
        index = self.run_combo.current()
        if 0 <= index < len(self.runs):
            return self.runs[index]
        return None

    def load_run(self) -> None:
        run = self._current_run()
        if run is None:
            return
        self.columns = store.history_columns(run.history)
        self.groups = store.group_channels(self.columns)
        self._fill_channels()
        self.app.set_context(run=run.path)
        self._load_series(run, self._default_selection())

    def _default_selection(self) -> list[str]:
        return [name for name in DEFAULT_CHANNELS if name in self.columns]

    def _fill_channels(self) -> None:
        tree = self.channel_tree
        tree.delete(*tree.get_children())
        order = ["接触力", "侵入量", "位移", "轨道位移", "速度", "角速度", "转角", "接触状态",
                 "时间", "其他"]
        for unit_group in sorted(self.groups, key=lambda name: (order.index(name)
                                                               if name in order else 99, name)):
            names = self.groups[unit_group]
            unit = store.channel_unit(names[0])
            parent = tree.insert("", "end", iid=f"group:{unit_group}", open=True,
                                 text=f"{unit_group}  [{unit}] · {len(names)}",
                                 tags=("unit",))
            for name in names:
                tree.insert(parent, "end", iid=f"chan:{name}",
                            text=store.channel_label(name))

    def _select(self, channels: list[str]) -> None:
        tree = self.channel_tree
        tree.selection_remove(*tree.selection())
        keep = [f"chan:{name}" for name in channels if name in self.columns]
        if keep:
            tree.selection_set(keep)
            tree.see(keep[0])

    def apply_preset(self, name: str) -> None:
        self._select([channel for channel in PRESETS[name] if channel in self.columns])
        self.draw_selected()

    def selected_channels(self) -> list[str]:
        picked = []
        for iid in self.channel_tree.selection():
            if iid.startswith("chan:"):
                picked.append(iid.split(":", 1)[1])
        return picked

    def _load_series(self, run: store.RunInfo, channels: list[str]) -> None:
        if not channels:
            self.series = None
            self._render_empty("该运行没有默认通道，左侧选择后再画")
            return
        self.app.set_status(f"加载 {run.name} 的 {len(channels)} 个通道 …", tone="run")
        path = run.history

        def work() -> store.Series:
            return store.read_history(path, ["time_s", *channels])

        def done(ok: bool, result, error) -> None:
            if not ok:
                self.app.set_status(f"读取失败：{error}", tone="fail")
                return
            self.series = result
            self.set_rows(result.rows,
                          f"{Path(run.history).parent.name} · {result.rows} 采样 · "
                          f"{result.rate_hz:.0f} Hz")
            self.summary_var.set(
                f"{run.name}\n{result.rows} 采样 · {result.rate_hz:.0f} Hz · "
                f"{len(self.columns)} 通道可选\n跨度 {result.span_s:.3f} s")
            self._select(channels)
            self.draw_selected()
            self.app.set_status(f"已加载 {run.name}：{result.rows} 行", tone="pass")

        self.app.submit("读取 history.csv", work, done)

    def draw_selected(self) -> None:
        channels = self.selected_channels()
        if self.series is None or not channels:
            self._render_empty("在左侧选择通道" if self.series is not None else "等待数据")
            return
        by_group: dict[str, list[str]] = {}
        for name in channels:
            by_group.setdefault(store.channel_group(name), []).append(name)
        limit = max(200, int(self.max_points_var.get() or MAX_POINTS))
        shown = 0
        drawn_series = 0
        self.drawn = 0
        for index, chart in enumerate(self.charts):
            if index >= len(by_group) or index >= MAX_GROUPS:
                chart.clear()
                chart.grid_remove()
                continue
            group = list(by_group)[index]
            names = by_group[group]
            series_list = []
            for position, name in enumerate(names):
                values = self.series.values.get(name)
                if values is None:
                    continue
                xs, ys = store.decimate(self.series.time_s, values, limit)
                series_list.append(ChartSeries(store.channel_label(name), xs, ys,
                                               theme.SERIES[(index + position) % len(theme.SERIES)]))
            chart.grid()
            chart.set_series(series_list, ylabel=f"{group} [{store.channel_unit(names[0])}]",
                             xlabel="时间 [s]")
            shown += 1
            drawn_series += len(series_list)
        self.drawn = drawn_series
        hidden = max(0, len(by_group) - MAX_GROUPS)
        note = f" · 另有 {hidden} 组未显示" if hidden else ""
        self.set_rows(self.series.rows if self.series else 0,
                      f"{len(self.columns)} 通道可选 → 已选 {len(channels)} → "
                      f"{shown} 个纵轴组 / {drawn_series} 条曲线{note}")
        self.summary_var.set(self.summary_var.get().split(" · 已画")[0] +
                             f" · 已画 {drawn_series} 条")

    def _render_empty(self, hint: str) -> None:
        for index, chart in enumerate(self.charts):
            if index == 0:
                chart.grid()
                chart.clear()
                chart.empty_hint = hint
                chart.clear()
            else:
                chart.clear()
                chart.grid_remove()

    # -- view controls -----------------------------------------------------
    def zoom(self, factor: float) -> None:
        for chart in self.charts:
            if chart.winfo_ismapped():
                chart.zoom_x(factor)

    def pan(self, fraction: float) -> None:
        for chart in self.charts:
            if chart.winfo_ismapped():
                chart.pan_x(fraction)

    def reset_zoom(self) -> None:
        for chart in self.charts:
            chart.reset_view()

    def export_figure(self) -> None:
        if not any(chart.winfo_ismapped() for chart in self.charts):
            self.app.set_status("没有可导出的曲线", tone="warn")
            return
        target = filedialog.asksaveasfilename(
            parent=self, title="导出当前图", defaultextension=".png",
            initialfile="velch_timeseries.png",
            filetypes=[("PNG 图片", "*.png")])
        if not target:
            return
        saved = [chart.export_png(target.replace(".png", f"_{index + 1}.png"))
                 for index, chart in enumerate(self.charts) if chart.winfo_ismapped()]
        if any(saved):
            self.app.set_status(f"已导出 {sum(saved)} 个纵轴组到 {Path(target).parent}",
                                tone="pass")
        else:
            self.app.set_status("当前绘图后端是 Tk Canvas，不支持 PNG 导出", tone="warn")
