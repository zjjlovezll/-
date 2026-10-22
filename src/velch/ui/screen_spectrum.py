"""Screen ④「结果-频谱」: 1/3-octave bars and band RMS from ``velch.inverse.bands``.

The screen is a thin presenter: :func:`velch.ui.store.spectrum` calls
``third_octave_levels`` / ``band_metrics`` and the screen only draws what came back.  The
band edges shown in the table are the geometric thirds ``f·2^(±1/6)`` of each centre
frequency, i.e. exactly the bands the filter bank used.
"""
from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from . import store, theme
from .screen import Screen
from .widgets import Card, Chart, ChartSeries, ListPanel, MetricCard, ui_font

DEFAULT_CHANNEL = "axle1_right_normal_n"


class SpectrumScreen(Screen):
    name = "spectrum"
    title = "1/3 倍频程"
    subtitle = "调用 velch.inverse.bands 的 third_octave_levels / band_metrics，柱高即带宽 RMS"

    def _build(self) -> None:
        self.runs: list[store.RunInfo] = []
        self.columns: list[str] = []
        #: ``中文标签 -> 原始列名``。The combobox must show words a person can read while the
        #: maths keeps needing the exact column name, so the mapping lives next to the widget
        #: instead of being re-derived from the label (labels are not guaranteed injective).
        self._column_by_label: dict[str, str] = {}
        self.result: store.SpectrumResult | None = None
        self.run_var = tk.StringVar()
        self.channel_var = tk.StringVar()
        self.low_var = tk.StringVar(value="5")
        self.high_var = tk.StringVar(value="1000")
        self.caption_var = tk.StringVar(value="尚未计算")

        self.columnconfigure(0, minsize=320)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = Card(self, "频带设置")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, theme.SPACE["3"]))
        body = left.body()
        ttk.Label(body, text="运行目录", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
        self.run_combo = ttk.Combobox(body, textvariable=self.run_var, state="readonly")
        self.run_combo.pack(fill="x", pady=(2, theme.SPACE["3"]))
        self.run_combo.bind("<<ComboboxSelected>>", lambda _e: self.load_run())

        ttk.Label(body, text="通道（单通道）", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
        self.channel_combo = ttk.Combobox(body, textvariable=self.channel_var, state="readonly")
        self.channel_combo.pack(fill="x", pady=(2, theme.SPACE["3"]))
        self.channel_combo.bind("<<ComboboxSelected>>", lambda _e: self.compute())

        band_row = ttk.Frame(body, style="Card.TFrame")
        band_row.pack(fill="x")
        for label, var in (("下限 Hz", self.low_var), ("上限 Hz", self.high_var)):
            cell = ttk.Frame(band_row, style="Card.TFrame")
            cell.pack(side="left", fill="x", expand=True, padx=(0, theme.GAP))
            ttk.Label(cell, text=label, style="Muted.TLabel",
                      font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
            ttk.Entry(cell, textvariable=var, style="Field.TEntry",
                      width=8).pack(fill="x")

        ttk.Button(body, text="计算频谱", style="Primary.TButton",
                   command=self.compute).pack(anchor="w", pady=theme.SPACE["3"])
        ttk.Label(body, text="方法：4 阶 Butterworth 带通 → 1/3 倍频程带内 RMS → "
                             "peak / p-p / rms / median|x| / p99.9 / 主导频带。",
                  style="Dim.TLabel", font=ui_font(theme.FONT_SIZE["micro"]),
                  wraplength=280, justify="left").pack(anchor="w")
        self.note_label = ttk.Label(body, textvariable=self.caption_var, style="Muted.TLabel",
                                    wraplength=280, justify="left")
        self.note_label.pack(anchor="w", pady=(theme.SPACE["2"], 0))

        right = ttk.Frame(self, style="Bg.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=3)
        right.rowconfigure(2, weight=2)

        metrics = ttk.Frame(right, style="Bg.TFrame")
        metrics.grid(row=0, column=0, sticky="ew", pady=(0, theme.SPACE["2"]))
        self.card_rms = MetricCard(metrics, "带宽 RMS", "—")
        self.card_rms.pack(side="left", padx=(0, theme.GAP))
        self.card_peak = MetricCard(metrics, "峰值", "—")
        self.card_peak.pack(side="left", padx=(0, theme.GAP))
        self.card_p2p = MetricCard(metrics, "峰峰值", "—")
        self.card_p2p.pack(side="left", padx=(0, theme.GAP))
        self.card_p999 = MetricCard(metrics, "p99.9", "—")
        self.card_p999.pack(side="left", padx=(0, theme.GAP))
        self.card_dom = MetricCard(metrics, "主导频带", "—")
        self.card_dom.pack(side="left", padx=(0, theme.GAP))

        self.chart = Chart(right, height=240, ylabel="带宽 RMS", xlabel="1/3 倍频程中心频率 [Hz]",
                           empty_hint="点「计算频谱」出图")
        self.chart.grid(row=1, column=0, sticky="nsew")

        table_card = Card(right, "带宽 RMS 明细")
        table_card.grid(row=2, column=0, sticky="nsew", pady=(theme.SPACE["2"], 0))
        self.table = ListPanel(table_card.body(), height=8)
        self.table.pack(fill="both", expand=True)
        self.table.columns((("centre", "中心频率 Hz", 110), ("band", "带宽 Hz", 120),
                            ("rms", "带宽 RMS", 110), ("share", "能量占比", 90)))

    # -- data --------------------------------------------------------------
    def refresh(self) -> None:
        self.runs = [run for run in store.scan_runs() if run.columns and not run.problem]
        self.run_combo.configure(values=[store.run_label(run) for run in self.runs])
        wanted = self.app.context.get("run")
        index = 0
        if wanted is not None:
            for position, run in enumerate(self.runs):
                if run.path == Path(wanted):
                    index = position
                    break
        if self.runs:
            self.run_combo.current(index)
            self.load_run()
        self.set_rows(len(self.runs), f"{len(self.runs)} 个可分析运行目录")

    def load_run(self) -> None:
        index = self.run_combo.current()
        if not (0 <= index < len(self.runs)):
            return
        run = self.runs[index]
        try:
            self.columns = [name for name in store.history_columns(run.history)
                            if name != "time_s"]
        except store.StoreError as exc:
            self.app.set_status(str(exc), tone="fail")
            return
        ordered = [name for name in self.columns if name.endswith("_normal_n")]
        ordered += [name for name in self.columns if name not in ordered]
        labels: list[str] = []
        self._column_by_label = {}
        for column in ordered:
            label = store.channel_label(column)
            if label in self._column_by_label:
                # Two columns that read the same in words must stay distinguishable in the
                # dropdown, otherwise one of them becomes unreachable.
                label = f"{label}（{column}）"
            self._column_by_label[label] = column
            labels.append(label)
        self.channel_combo.configure(values=labels)
        pick_column = DEFAULT_CHANNEL if DEFAULT_CHANNEL in ordered else (ordered[0] if ordered else "")
        pick = next((label for label, column in self._column_by_label.items()
                     if column == pick_column), "")
        self.channel_var.set(pick)
        self.app.set_context(run=run.path)
        self.set_rows(len(ordered), f"{run.name} · {len(ordered)} 个可分析通道")
        self.compute()

    def compute(self) -> None:
        index = self.run_combo.current()
        # The dropdown holds Chinese labels; the maths needs the exact column name.
        channel = self._column_by_label.get(self.channel_var.get(), self.channel_var.get())
        if not (0 <= index < len(self.runs)) or not channel:
            self.app.set_status("先选运行目录与通道", tone="warn")
            return
        run = self.runs[index]
        try:
            low = float(self.low_var.get())
            high = float(self.high_var.get())
        except ValueError:
            self.app.set_status("频带上下限必须是数字", tone="fail")
            return
        if high <= low:
            self.app.set_status("上限必须大于下限", tone="fail")
            return
        self.app.set_status(
            f"计算 {run.name} / {store.channel_short_label(channel)}（{channel}）的 1/3 倍频程 …",
            tone="run",
        )

        def work() -> store.SpectrumResult:
            series = store.read_history(run.history, ["time_s", channel])
            return store.spectrum(series, channel, low, high)

        def done(ok: bool, result, error) -> None:
            if not ok:
                self.app.set_status(f"频谱计算失败：{error}", tone="fail")
                self.caption_var.set(f"失败：{error}")
                return
            self.result = result
            self._render(result)

        self.app.submit("1/3 倍频程", work, done)

    def _render(self, result: store.SpectrumResult) -> None:
        unit = store.channel_unit(result.column)
        metrics = result.metrics
        bands = result.band_table()
        centres = [band for band, _level in bands if band > 0]
        levels = [level for band, level in bands if band > 0]
        positions = [math.log10(centre) for centre in centres]
        self.chart.set_series(
            [ChartSeries(store.channel_label(result.column), positions, levels,
                         theme.ACCENT, kind="bar", width=0.8)],
            ylabel=f"带宽 RMS [{unit}]",
            xlabel="1/3 倍频程中心频率 [Hz]（对数等宽）",
            x_ticks=[(position, f"{centre:g}") for position, centre in zip(positions, centres)])

        total = sum(level * level for level in levels) or 1.0
        self.table.clear()
        for order, (centre, level) in enumerate(bands):
            low = centre / 2 ** (1 / 6)
            high = centre * 2 ** (1 / 6)
            share = (level * level / total) * 100.0
            self.table.tree.insert("", "end", iid=str(order),
                                   values=(f"{centre:.1f}", f"{low:.1f} – {high:.1f}",
                                           f"{level:.4g}", f"{share:.2f} %"))
        self.card_rms.set(f"{metrics.rms:.4g}", unit)
        self.card_peak.set(f"{metrics.peak:.4g}", unit)
        self.card_p2p.set(f"{metrics.peak_to_peak:.4g}", unit)
        self.card_p999.set(f"{metrics.p999_abs:.4g}", unit)
        self.card_dom.set("-" if result.dominant_hz is None
                          else f"{result.dominant_hz:.0f}", "Hz")
        caption = (f"{store.channel_short_label(result.column)}（{result.column}） · "
                   f"采样 {result.rate_hz:.0f} Hz · "
                   f"频带 {result.low_hz:g}–{result.high_hz:g} Hz · {len(bands)} 个 1/3 倍频程带")
        if result.note:
            caption += "\n" + result.note
        self.caption_var.set(caption)
        self.set_rows(len(bands), f"{len(bands)} 个频带 · 主导 {result.dominant_hz:.0f} Hz")
        self.app.set_status(f"已计算 {len(bands)} 个 1/3 倍频程带", tone="pass")

    def export_figure(self) -> None:
        from tkinter import filedialog
        target = filedialog.asksaveasfilename(parent=self, title="导出频谱图",
                                              defaultextension=".png",
                                              initialfile="velch_spectrum.png",
                                              filetypes=[("PNG 图片", "*.png")])
        if not target:
            return
        if self.chart.export_png(target):
            self.app.set_status(f"已导出 {target}", tone="pass")
        else:
            self.app.set_status("当前绘图后端是 Tk Canvas，不支持 PNG 导出", tone="warn")
