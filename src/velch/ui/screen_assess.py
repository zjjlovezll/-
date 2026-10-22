"""Screen ⑤「评价」: the seven manifest gates plus the three GB/T limit bars.

Two independent sources of truth are shown side by side and never mixed:

* the manifest's seven gates (did the solver's own checks pass?), read straight from
  ``manifest.json``;
* ``velch assess``'s three limit checks (脱轨系数 / 轮重减载率 / 轮轴横向力), computed by
  calling the same public function the CLI uses (``velch.metrics.assess_history``).

The 「运行 velch assess」 button additionally launches the real CLI so the exit code
(0 通过 / 2 超限) is visible in the window.
"""
from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from . import store, theme
from .screen import Screen
from .widgets import Card, Chip, GateList, LimitBar, ListPanel, MetricCard, ui_font

AXLE_COLUMNS = (
    ("axle", "轴", 40),
    ("normal", "法向力范围 kN（左 / 右）", 168),
    ("derail", "脱轨系数", 84),
    ("reduce", "减载率", 72),
    ("lateral", "轮轴横向力 kN", 96),
)


class AssessScreen(Screen):
    name = "assess"
    title = "数值门与运用限值"
    subtitle = "manifest 七项数值门逐项判定 + assess 三项限值对比（脱轨系数 / 减载率 / 轮轴横向力）"

    def _build(self) -> None:
        self.runs: list[store.RunInfo] = []
        self.view: store.AssessmentView | None = None
        self.summary: dict = {}
        self.run_var = tk.StringVar()
        self.load_var = tk.StringVar(value="0")
        self.cli_var = tk.StringVar(value="velch assess 尚未运行")
        self.verdict_var = tk.StringVar(value="未评价")

        self.columnconfigure(0, minsize=330)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = Card(self, "评价对象")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, theme.SPACE["3"]))
        body = left.body()
        ttk.Label(body, text="运行目录", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
        self.run_combo = ttk.Combobox(body, textvariable=self.run_var, state="readonly")
        self.run_combo.pack(fill="x", pady=(2, theme.SPACE["3"]))
        self.run_combo.bind("<<ComboboxSelected>>", lambda _e: self.load_run())

        load_row = ttk.Frame(body, style="Card.TFrame")
        load_row.pack(fill="x")
        ttk.Label(load_row, text="静态轴重 N（0=自动）", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
        ttk.Entry(load_row, textvariable=self.load_var,
                  style="Field.TEntry").pack(fill="x", pady=(2, 0))

        actions = ttk.Frame(body, style="Card.TFrame")
        actions.pack(fill="x", pady=theme.SPACE["3"])
        ttk.Button(actions, text="重新评价", style="Primary.TButton",
                   command=self.load_run).pack(side="left")
        ttk.Button(actions, text="运行 velch assess", style="Ghost.TButton",
                   command=self.run_cli).pack(side="left", padx=(theme.GAP, 0))

        ttk.Label(body, textvariable=self.cli_var, style="Mono.TLabel",
                  wraplength=300, justify="left").pack(anchor="w")
        self.cli_log = tk.Text(body, height=6, width=24, bg=theme.BG, fg=theme.INK_MUTED,
                               font=(theme.FONT_MONO, theme.FONT_SIZE["micro"]),
                               relief="flat", highlightthickness=0, wrap="none",
                               state="disabled")
        self.cli_log.pack(fill="x", pady=(theme.SPACE["2"], 0))

        ttk.Label(body, text="口径说明", style="Section.TLabel").pack(
            anchor="w", pady=(theme.SPACE["4"], 2))
        ttk.Label(body, text="七项门来自 manifest.json 的 summary.gates，由求解器自己判定；"
                             "三项限值来自 velch.metrics.assess_history，与 CLI 共用同一实现。"
                             "两者互不替代：门是数值自检，限值是运用判据。",
                  style="Dim.TLabel", font=ui_font(theme.FONT_SIZE["micro"]),
                  wraplength=300, justify="left").pack(anchor="w")

        right = ttk.Frame(self, style="Bg.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        cards = ttk.Frame(right, style="Bg.TFrame")
        cards.grid(row=0, column=0, sticky="ew", pady=(0, theme.SPACE["2"]))
        self.card_verdict = MetricCard(cards, "总判定", "—")
        self.card_verdict.pack(side="left", padx=(0, theme.GAP))
        self.card_samples = MetricCard(cards, "样本", "—")
        self.card_samples.pack(side="left", padx=(0, theme.GAP))
        self.card_load = MetricCard(cards, "静态轴重", "—", "N")
        self.card_load.pack(side="left", padx=(0, theme.GAP))
        self.card_status = MetricCard(cards, "manifest 门", "—")
        self.card_status.pack(side="left", padx=(0, theme.GAP))

        panes = ttk.Frame(right, style="Bg.TFrame")
        panes.grid(row=1, column=0, sticky="nsew")
        panes.columnconfigure(0, weight=1, minsize=340)
        panes.columnconfigure(1, weight=1, minsize=420)
        panes.rowconfigure(0, weight=1)

        gates = Card(panes, "七项数值门")
        gates.grid(row=0, column=0, sticky="nsew", padx=(0, theme.SPACE["2"]))
        gbody = gates.body()
        self.gates = GateList(gbody)
        self.gates.pack(fill="x")
        self.gate_note = ttk.Label(gbody, text="", style="Dim.TLabel",
                                   font=ui_font(theme.FONT_SIZE["micro"]),
                                   wraplength=330, justify="left")
        self.gate_note.pack(anchor="w", pady=(theme.SPACE["3"], 0))

        limits = Card(panes, "三项限值")
        limits.grid(row=0, column=1, sticky="nsew")
        lbody = limits.body()
        self.bar_row = ttk.Frame(lbody, style="Card.TFrame")
        self.bar_row.pack(fill="x")
        self.bars: dict[str, LimitBar] = {}
        self.verdict_chip_row = ttk.Frame(lbody, style="Card.TFrame")
        self.verdict_chip_row.pack(fill="x", pady=(theme.SPACE["2"], 0))
        self.verdict_chip = Chip(self.verdict_chip_row, "未评价", "idle")
        self.verdict_chip.pack(side="left")
        ttk.Label(self.verdict_chip_row, textvariable=self.verdict_var, style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left",
                                                              padx=(theme.GAP, 0))
        self.axle_panel = ListPanel(lbody, height=7)
        self.axle_panel.pack(fill="both", expand=True, pady=(theme.SPACE["3"], 0))
        self.axle_panel.columns(AXLE_COLUMNS)

    # -- data --------------------------------------------------------------
    def refresh(self) -> None:
        self.runs = store.scan_runs()
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
        self.set_rows(len(self.runs), f"{len(self.runs)} 个运行目录可评价")

    def on_context(self) -> None:
        wanted = self.app.context.get("run")
        if wanted is None:
            return
        for position, run in enumerate(self.runs):
            if run.path == Path(wanted) and self.run_combo.current() != position:
                self.run_combo.current(position)
                self.load_run()
                return

    def _current_run(self) -> store.RunInfo | None:
        index = self.run_combo.current()
        return self.runs[index] if 0 <= index < len(self.runs) else None

    def load_run(self) -> None:
        run = self._current_run()
        if run is None:
            return
        self.app.set_context(run=run.path)
        self.summary = self._read_summary(run)
        self._render_gates(run)

        raw = self.load_var.get().strip()
        try:
            static_load = float(raw) if raw else 0.0
        except ValueError:
            self.app.set_status("静态轴重必须是数字", tone="fail")
            return
        try:
            self.view = store.assess(run.path, static_load or None)
        except Exception as exc:  # AssessmentError or a missing column
            self.view = None
            self.app.set_status(f"评价失败：{type(exc).__name__}: {exc}", tone="fail")
            self.verdict_var.set(f"评价失败：{exc}")
            self.verdict_chip.set("失败", "fail")
            self.set_rows(0, f"{run.name} 评价失败")
            return
        self._render_limits(run, self.view)

    def _read_summary(self, run: store.RunInfo) -> dict:
        try:
            payload = json.loads(run.manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        summary = payload.get("summary")
        return summary if isinstance(summary, dict) else {}

    # -- gates -------------------------------------------------------------
    def _gate_detail(self, key: str) -> str:
        summary = self.summary
        if key == "solver_completed":
            solver = summary.get("solver") if isinstance(summary.get("solver"), dict) else {}
            method = solver.get("method") or "—"
            nfev = solver.get("nfev")
            steps = summary.get("steps")
            bits = [str(method)]
            if isinstance(nfev, (int, float)):
                bits.append(f"nfev {nfev:.0f}")
            if isinstance(steps, (int, float)):
                bits.append(f"步数 {steps:.0f}")
            return " · ".join(bits)
        if key == "finite_states_and_forces":
            return "状态与力均有限" if summary.get(key) else "—"
        field = store.GATE_DETAIL_FIELDS.get(key)
        if not field:
            return "—"
        value = summary.get(field)
        unit = store.GATE_UNITS.get(field, "")
        if isinstance(value, (int, float)):
            return f"{value:.4g} {unit}".strip()
        return "—"

    def _render_gates(self, run: store.RunInfo) -> None:
        self.gates.build([(key, label, self._gate_detail(key))
                          for key, label in store.GATE_LABELS])
        passed = 0
        known = 0
        for key, _label in store.GATE_LABELS:
            value = run.gates.get(key)
            self.gates.set(key, value, self._gate_detail(key))
            if value is None:
                continue
            known += 1
            passed += 1 if value else 0
        self.card_status.set(f"{passed}/{known}" if known else "—",
                            tone=theme.PASS if known and passed == known else theme.FAIL
                            if known else theme.INK_MUTED)
        failed = [label for key, label in store.GATE_LABELS if run.gates.get(key) is False]
        note = run.peak_force_kn
        text = (f"算例 {run.case_id or '—'} · 总自由度 {run.total_dof or '—'} · "
                f"峰值法向力 {'—' if note is None else f'{note/1000:.1f} kN'}")
        if failed:
            text += "\n未通过：" + "、".join(failed)
        self.gate_note.configure(text=text)
        self.set_rows(known, f"{run.name} · {passed}/{known} 门通过")

    # -- limits ------------------------------------------------------------
    def _render_limits(self, run: store.RunInfo, view: store.AssessmentView) -> None:
        bars = view.bars()
        for bar in self.bars.values():
            bar.destroy()
        self.bars.clear()
        for label, value, limit, passed, caption in bars:
            bar = LimitBar(self.bar_row, label, caption=caption)
            bar.pack(fill="x", pady=(0, theme.SPACE["2"]))
            bar.set(value, limit, passed, caption)
            self.bars[label] = bar
            self.bar_row.update_idletasks()
            bar._draw()

        assessment = view.assessment
        self.card_verdict.set("通过" if view.passed else "超限",
                              tone=theme.PASS if view.passed else theme.FAIL)
        self.card_samples.set(f"{assessment.samples}")
        self.card_load.set(f"{assessment.static_axle_load_n:.0f}")
        self.verdict_chip.set("全部限值通过" if view.passed else "存在超限项",
                              "pass" if view.passed else "fail")
        worst = [f"{label} {value:.4g} > {limit:.4g}"
                 for label, value, limit, passed, _caption in bars if not passed]
        self.verdict_var.set("；".join(worst) if worst else "三项限值均在界内")

        self.axle_panel.clear()
        for order, axle in enumerate(assessment.axles):
            self.axle_panel.tree.insert(
                "", "end", iid=str(order),
                values=(str(axle.axle_index),
                        f"{axle.normal_left_min_n/1000:.1f}–{axle.normal_left_max_n/1000:.1f}"
                        f" / {axle.normal_right_min_n/1000:.1f}–"
                        f"{axle.normal_right_max_n/1000:.1f}",
                        f"{axle.derailment_coefficient:.3f} ({axle.derailment_side})",
                        f"{axle.wheel_load_reduction:.3f}",
                        f"{axle.lateral_force_n/1000:.2f}"))
        self.set_rows(len(assessment.axles),
                      f"{run.name} · {assessment.samples} 采样 · "
                      f"{len(bars)} 项限值 · {'通过' if view.passed else '超限'}")
        self.app.set_status(
            f"{run.name}：{'三项限值通过' if view.passed else '存在超限项'} · "
            f"样本 {assessment.samples}", tone="pass" if view.passed else "fail")

    # -- CLI ---------------------------------------------------------------
    def run_cli(self) -> None:
        run = self._current_run()
        if run is None:
            self.app.set_status("先选一个运行目录", tone="warn")
            return
        if self.app.process is not None and self.app.process.running:
            self.app.set_status("已有子进程在运行", tone="warn")
            return
        self.cli_log.configure(state="normal")
        self.cli_log.delete("1.0", "end")
        self.cli_log.configure(state="disabled")
        argv = [sys.executable, "-X", "utf8", "-m", "velch", "assess", str(run.path)]
        self.cli_var.set("$ " + " ".join(argv))
        self.app.spawn(argv, store.REPO_ROOT, owner=self.name)
        self.app.set_state("running")
        self.app.set_status("正在运行 velch assess …", tone="run")

    def on_log(self, line: str) -> None:
        self.cli_log.configure(state="normal")
        self.cli_log.insert("end", line + "\n")
        self.cli_log.see("end")
        self.cli_log.configure(state="disabled")

    def on_process_exit(self, code: int, elapsed: float, cancelled: bool) -> None:
        if cancelled:
            self.cli_var.set("velch assess 已取消")
            return
        verdict = {0: "通过（退出码 0）", 2: "超限（退出码 2）"}.get(code, f"异常退出码 {code}")
        self.cli_var.set(f"velch assess {verdict} · 用时 {elapsed:.1f} s")
        self.app.set_status(f"velch assess {verdict}", tone="pass" if code == 0 else "fail")

    def export_figure(self) -> None:
        self.app.set_status("评价屏的条形图可用截图保存")
