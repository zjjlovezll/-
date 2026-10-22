"""Screen ⑥「对照」: Velch against Simpack (or a measured CSV) on one station axis.

Both sides keep their own definitions; the screen only resamples them onto a shared station
grid and reports peak / RMS differences.  The comparison is explicitly **口径对照**, not a
same-turnout validation, and the banner says so on every load — the caveat is part of the
product, not a footnote the reader has to hunt for.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from . import store, theme
from .fmt import fmt_number, fmt_percent
from .screen import Screen
from .widgets import Card, Chart, ChartSeries, Chip, ListPanel, ui_font

STATIC_CAVEAT = ("非同一道岔时只作口径对照：两侧共用同一里程轴、同一通道定义与同一频带口径，"
                 "力与位移的差异可以直接读，但不构成同工况验证。")
STATS_COLUMNS = (("metric", "指标", 150), ("ours", "Velch", 100),
                 ("theirs", "对照", 100), ("delta", "差值", 100),
                 ("pct", "相对差", 84))


class CompareScreen(Screen):
    name = "compare"
    title = "与 Simpack / 实测同轴叠加"
    subtitle = "Velch 与 Simpack/实测同里程轴叠画，给出峰值与 RMS 差；非同工况只作口径对照"

    def _build(self) -> None:
        self.runs: list[store.RunInfo] = []
        self.result: store.CompareResult | None = None
        self.ours: store.ReferenceSeries | None = None
        self.theirs: store.ReferenceSeries | None = None
        self.csv_path: Path | None = None
        self.csv_columns: list[str] = []

        self.source_var = tk.StringVar(value="simpack")
        self.run_var = tk.StringVar()
        self.csv_var = tk.StringVar(value="（未选择实测 CSV）")
        self.station_col = tk.StringVar()
        self.force_col = tk.StringVar()
        self.scale_var = tk.StringVar(value="1")
        self.low_var = tk.StringVar()
        self.high_var = tk.StringVar()
        self.points_var = tk.IntVar(value=400)
        self.caveat_var = tk.StringVar(value=STATIC_CAVEAT)

        self.columnconfigure(0, minsize=int(340 * theme.SCALE))
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        banner = tk.Frame(self, bg=theme.RAISED, highlightthickness=0)
        banner.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, theme.SPACE["3"]))
        Chip(banner, "口径提示", "warn").pack(side="left", padx=(theme.SPACE["3"],
                                                                theme.GAP))
        tk.Label(banner, textvariable=self.caveat_var, bg=theme.RAISED, fg=theme.INK,
                 justify="left", anchor="w", wraplength=900,
                 font=ui_font(theme.FONT_SIZE["tiny"])).pack(
            side="left", fill="x", expand=True, pady=theme.SPACE["2"])

        left = Card(self, "对照设置")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, theme.SPACE["3"]))
        body = left.body()

        ttk.Label(body, text="对照源", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
        available, reason = store.simpack_available()
        self.radio_simpack = ttk.Radiobutton(body, text="Simpack 350.mat（前轮对右轨）",
                                             value="simpack", variable=self.source_var,
                                             style="TRadiobutton",
                                             command=self.on_source)
        self.radio_simpack.pack(anchor="w")
        if not available:
            self.radio_simpack.state(["disabled"])
            self.source_var.set("csv")
        ttk.Label(body, text=reason or f"{store.SIMPACK_MAT.name} · {store.SIMPACK_GROUP}",
                  style="Dim.TLabel", font=ui_font(theme.FONT_SIZE["micro"]),
                  wraplength=300, justify="left").pack(anchor="w")
        ttk.Radiobutton(body, text="实测 CSV（自选列）", value="csv",
                        variable=self.source_var, style="TRadiobutton",
                        command=self.on_source).pack(anchor="w", pady=(2, 0))

        csv_row = ttk.Frame(body, style="Card.TFrame")
        csv_row.pack(fill="x", pady=(theme.SPACE["2"], 0))
        ttk.Button(csv_row, text="选择 CSV", style="Ghost.TButton",
                   command=self.choose_csv).pack(side="left")
        ttk.Label(csv_row, textvariable=self.csv_var, style="Dim.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"]), wraplength=200).pack(
            side="left", padx=(theme.GAP, 0))

        map_row = ttk.Frame(body, style="Card.TFrame")
        map_row.pack(fill="x", pady=(2, 0))
        ttk.Label(map_row, text="站点列", style="Muted.TLabel").pack(side="left")
        self.station_combo = ttk.Combobox(map_row, textvariable=self.station_col,
                                          state="readonly", width=14)
        self.station_combo.pack(side="left")
        ttk.Label(map_row, text="→", style="Dim.TLabel").pack(side="left", padx=2)
        ttk.Label(map_row, text="力列", style="Muted.TLabel").pack(
            side="left", padx=(theme.PAD, 0))
        self.force_combo = ttk.Combobox(map_row, textvariable=self.force_col,
                                        state="readonly", width=14)
        self.force_combo.pack(side="left")
        scale_row = ttk.Frame(body, style="Card.TFrame")
        scale_row.pack(fill="x", pady=(2, 0))
        ttk.Label(scale_row, text="力单位系数（CSV→N）", style="Dim.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left")
        ttk.Entry(scale_row, textvariable=self.scale_var, width=8,
                  style="Field.TEntry").pack(side="left", padx=(theme.GAP, 0))

        ttk.Separator(body).pack(fill="x", pady=theme.SPACE["3"])
        ttk.Label(body, text="Velch 运行目录", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
        self.run_combo = ttk.Combobox(body, textvariable=self.run_var, state="readonly")
        self.run_combo.pack(fill="x", pady=(2, theme.SPACE["2"]))
        self.run_combo.bind("<<ComboboxSelected>>", lambda _e: self.set_rows(len(self.runs)))

        window_row = ttk.Frame(body, style="Card.TFrame")
        window_row.pack(fill="x")
        for label, var in (("里程下限 m", self.low_var), ("里程上限 m", self.high_var)):
            cell = ttk.Frame(window_row, style="Card.TFrame")
            cell.pack(side="left", fill="x", expand=True, padx=(0, theme.GAP))
            ttk.Label(cell, text=label, style="Dim.TLabel",
                      font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
            ttk.Entry(cell, textvariable=var, style="Field.TEntry").pack(fill="x")
        points_row = ttk.Frame(body, style="Card.TFrame")
        points_row.pack(fill="x", pady=(theme.SPACE["2"], 0))
        ttk.Label(points_row, text="里程采样点", style="Dim.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left")
        ttk.Spinbox(points_row, from_=50, to=4000, increment=50,
                    textvariable=self.points_var, width=6,
                    style="TSpinbox").pack(side="left", padx=(theme.GAP, 0))

        ttk.Button(body, text="计算对照", style="Primary.TButton",
                   command=self.compute).pack(anchor="w", pady=theme.SPACE["3"])
        self.status_label = ttk.Label(body, text="", style="Muted.TLabel",
                                      wraplength=300, justify="left")
        self.status_label.pack(anchor="w")

        right = ttk.Frame(self, style="Bg.TFrame")
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(2, weight=1)

        # One empty state, one sentence: two different phrasings for the same condition read as
        # two different states.
        self.chart_force = Chart(right, height=200, ylabel="法向力 [kN]",
                                 xlabel="里程 [m]",
                                 empty_hint="点「计算对照」叠加曲线与差值")
        self.chart_force.grid(row=0, column=0, sticky="nsew", pady=(0, theme.SPACE["2"]))
        self.chart_z = Chart(right, height=170, ylabel="轮对垂向位移（相对均值）[mm]",
                             xlabel="里程 [m]",
                             empty_hint="点「计算对照」叠加曲线与差值")
        self.chart_z.grid(row=1, column=0, sticky="nsew", pady=(0, theme.SPACE["2"]))

        stats_card = Card(right, "差值统计")
        stats_card.grid(row=2, column=0, sticky="nsew")
        self.stats_panel = ListPanel(stats_card.body(), height=5)
        self.stats_panel.pack(fill="both", expand=True)
        self.stats_panel.columns(STATS_COLUMNS)

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
        available, reason = store.simpack_available()
        if not available:
            self.source_var.set("csv")
            self.status_label.configure(text=f"Simpack 不可用：{reason}")
        self.on_source()
        self.set_rows(len(self.runs), f"{len(self.runs)} 个 Velch 运行目录")

    def on_source(self) -> None:
        csv_on = self.source_var.get() == "csv"
        for widget in (self.station_combo, self.force_combo):
            widget.configure(state="readonly" if csv_on else "disabled")

    def choose_csv(self) -> None:
        target = filedialog.askopenfilename(parent=self, title="选择实测 CSV",
                                           initialdir=str(store.VALIDATION_DIR),
                                           filetypes=[("CSV 数据", "*.csv"),
                                                      ("全部文件", "*.*")])
        if not target:
            return
        self.csv_path = Path(target)
        self.csv_var.set(self.csv_path.name)
        try:
            self.csv_columns = store.history_columns(self.csv_path)
        except store.StoreError as exc:
            self.app.set_status(str(exc), tone="fail")
            return
        self.station_combo.configure(values=self.csv_columns)
        self.force_combo.configure(values=self.csv_columns)
        numeric = [name for name in self.csv_columns
                   if any(token in name.lower() for token in ("station", "x", "里程", "s_m"))]
        self.station_col.set(numeric[0] if numeric else self.csv_columns[0])
        force = [name for name in self.csv_columns
                 if any(token in name.lower() for token in ("force", "normal", "力", "_n"))]
        self.force_col.set(force[-1] if force else self.csv_columns[-1])
        self.source_var.set("csv")
        self.on_source()

    # -- compute -----------------------------------------------------------
    def compute(self) -> None:
        index = self.run_combo.current()
        if not (0 <= index < len(self.runs)):
            self.app.set_status("先选一个 Velch 运行目录", tone="warn")
            return
        run = self.runs[index]
        source = self.source_var.get()
        if source == "csv" and (self.csv_path is None or not self.station_col.get()
                                or not self.force_col.get()):
            self.app.set_status("实测 CSV 需要路径、里程列与力列", tone="warn")
            return
        try:
            scale = float(self.scale_var.get() or 1.0)
        except ValueError:
            self.app.set_status("单位系数必须是数字", tone="fail")
            return
        low_raw = self.low_var.get().strip()
        high_raw = self.high_var.get().strip()
        window = None
        try:
            if low_raw and high_raw:
                window = (float(low_raw), float(high_raw))
        except ValueError:
            self.app.set_status("里程窗必须是数字", tone="fail")
            return
        points = max(50, int(self.points_var.get() or 400))
        self.app.set_status("读取两侧数据并重采样 …", tone="run")

        def work():
            ours = store.velch_reference(run.path)
            if source == "simpack":
                theirs = store.simpack_reference()
            else:
                theirs = store.measured_reference(self.csv_path, self.station_col.get(),
                                                  self.force_col.get(), scale)
            return ours, theirs, store.compare(ours, theirs, window, points)

        def done(ok: bool, result, error) -> None:
            if not ok:
                self.app.set_status(f"对照失败：{error}", tone="fail")
                self.status_label.configure(text=f"对照失败：{error}")
                self.caveat_var.set(STATIC_CAVEAT)
                return
            ours, theirs, comparison = result
            self.ours, self.theirs, self.result = ours, theirs, comparison
            self._render(comparison)

        self.app.submit("对照重采样", work, done)

    def _render(self, result: store.CompareResult) -> None:
        xs = result.grid_m
        force_ours = result.ours["force_n"] / 1000.0
        force_theirs = result.theirs["force_n"] / 1000.0
        self.chart_force.set_series(
            [ChartSeries("Velch", xs, force_ours, theme.ACCENT),
             ChartSeries(self.theirs.label if self.theirs else "对照", xs, force_theirs,
                         theme.AMBER)],
            ylabel="法向力 [kN]", xlabel="里程 [m]")
        series_count = 2
        if "wheel_z_m" in result.ours and "wheel_z_m" in result.theirs:
            za = (result.ours["wheel_z_m"] - result.ours["wheel_z_m"].mean()) * 1e3
            zb = (result.theirs["wheel_z_m"] - result.theirs["wheel_z_m"].mean()) * 1e3
            self.chart_z.set_series(
                [ChartSeries("Velch", xs, za, theme.ACCENT),
                 ChartSeries(self.theirs.label if self.theirs else "对照", xs, zb, theme.AMBER)],
                ylabel="轮对垂向位移（相对均值）[mm]", xlabel="里程 [m]")
            series_count += 2
        else:
            self.chart_z.clear()

        self.stats_panel.clear()
        for order, (metric, ours, theirs, delta) in enumerate(result.summary_rows()):
            # NaN renders as "+nan %" through an f-string, and a reader cannot tell that from a
            # real ratio; fmt_number gives the em dash and keeps one formatting path.
            pct = "—" if abs(theirs) < 1e-9 else fmt_percent(delta / theirs, signed=True)
            self.stats_panel.tree.insert("", "end", iid=str(order),
                                         values=(metric, fmt_number(ours), fmt_number(theirs),
                                                 fmt_number(delta, signed=True), pct))
        self.stats_panel.restripe()
        self.caveat_var.set(result.caveat or STATIC_CAVEAT)
        rows = len(result.summary_rows())
        span = f"{xs.min():.2f}–{xs.max():.2f} m"
        self.status_label.configure(
            text=f"两侧各 {len(xs)} 点 · 共里程窗 {span} · {series_count} 条曲线\n"
                 f"Velch：{self.ours.label if self.ours else '—'}\n"
                 f"对照：{self.theirs.label if self.theirs else '—'}")
        self.set_rows(rows + series_count,
                      f"{rows} 项差值 · {series_count} 条曲线 · 里程窗 {span}")
        self.app.set_status(f"对照完成：{rows} 项差值，里程窗 {span}", tone="pass")

    def export_figure(self) -> None:
        target = filedialog.asksaveasfilename(parent=self, title="导出对照图",
                                              defaultextension=".png",
                                              initialfile="velch_compare.png",
                                              filetypes=[("PNG 图片", "*.png")])
        if not target:
            return
        stem = target[:-4] if target.lower().endswith(".png") else target
        ok = self.chart_force.export_png(stem + "_force.png")
        ok = self.chart_z.export_png(stem + "_wheel_z.png") or ok
        self.app.set_status("已导出对照图" if ok else
                            "当前绘图后端是 Tk Canvas，不支持 PNG 导出",
                            tone="pass" if ok else "warn")
