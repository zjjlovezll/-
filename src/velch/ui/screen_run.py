"""Screen ②「运行」: launch the CLI, stream its stdout, cancel, batch in parallel.

The screen never imports the solver.  It builds an argv for
``run-vehicle`` / ``run-vehicle-batch``, spawns it through :meth:`velch.ui.app.VelchUI.spawn`
and only reads the streamed lines — so a solver crash cannot take the window down and a
UI crash cannot corrupt a run.
"""
from __future__ import annotations

import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from . import store, theme
from .screen import Screen
from .widgets import Card, ListPanel, MetricCard, ui_font

MAX_LOG_LINES = 4000


class RunScreen(Screen):
    name = "run"
    title = "启动 CLI 与日志"
    subtitle = "选算例 → 设输出目录 → 启动 CLI 子进程，实时查看 stdout 与耗时；可取消、可批量"

    #: First entry of each pair means "keep whatever the case file declares".
    METHOD_CHOICES = ("按算例声明", "显式 DOP853", "隐式 Radau", "隐式 BDF")
    METHOD_VALUES = ("", "DOP853", "Radau", "BDF")
    JACOBIAN_CHOICES = ("按算例声明", "解析（隐式专用）", "稀疏差分", "不用")
    JACOBIAN_VALUES = ("", "analytic", "sparse_fd", "none")

    def _build(self) -> None:
        self.cases: list[store.CaseInfo] = []
        self.log_lines = 0
        self.seen_bytes = 0
        self.output_dir: Path | None = None
        self.status_var = tk.StringVar(value="未启动")
        self.elapsed_var = tk.StringVar(value="—")
        self.lines_var = tk.StringVar(value="0")
        self.codes_var = tk.StringVar(value="—")
        self.outdir_var = tk.StringVar(value=str(store.VALIDATION_DIR / "out_ui_run"))
        self.jobs_var = tk.IntVar(value=1)
        self.autoscroll_var = tk.BooleanVar(value=True)

        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=5)
        self.rowconfigure(0, weight=1)

        # -- left: configuration -----------------------------------------
        left = Card(self, "运行配置")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, theme.SPACE["3"]))
        body = left.body()

        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)   # the case list is the only elastic row

        ttk.Label(body, text="算例（多选即批量）", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).grid(row=0, column=0, sticky="w")
        self.case_list = ListPanel(body, height=10, selectmode="extended")
        self.case_list.grid(row=1, column=0, sticky="nsew", pady=(2, theme.SPACE["2"]))
        self.case_list.columns((("case_id", "算例", 200), ("duration", "时长", 70),
                                ("dof", "自由度", 60)))

        out_row = ttk.Frame(body, style="Card.TFrame")
        out_row.grid(row=2, column=0, sticky="ew", pady=(theme.SPACE["2"], 0))
        ttk.Label(out_row, text="输出目录 / 批量根目录", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
        entry_row = ttk.Frame(out_row, style="Card.TFrame")
        entry_row.pack(fill="x")
        ttk.Entry(entry_row, textvariable=self.outdir_var,
                  style="Field.TEntry").pack(side="left", fill="x", expand=True)
        ttk.Button(entry_row, text="浏览", style="Ghost.TButton",
                   command=self.choose_dir).pack(side="left", padx=(theme.GAP, 0))

        jobs_row = ttk.Frame(body, style="Card.TFrame")
        jobs_row.grid(row=3, column=0, sticky="ew", pady=theme.SPACE["2"])
        ttk.Label(jobs_row, text="并行 --jobs", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left")
        ttk.Spinbox(jobs_row, from_=1, to=16, textvariable=self.jobs_var, width=4,
                    style="TSpinbox").pack(side="left", padx=(theme.GAP, 0))
        ttk.Checkbutton(jobs_row, text="自动滚动日志", variable=self.autoscroll_var,
                        style="TCheckbutton").pack(side="left", padx=(theme.PAD, 0))

        solver_row = ttk.Frame(body, style="Card.TFrame")
        solver_row.grid(row=4, column=0, sticky="ew", pady=(0, theme.SPACE["2"]))
        ttk.Label(solver_row, text="求解器（算例文件本身不改，另派生 case_used.json）",
                  style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
        self.fast_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(solver_row, text="快速预设（BDF + 解析雅可比 + rtol 1e-4）",
                        variable=self.fast_var, style="TCheckbutton").pack(anchor="w")
        hint = ttk.Label(solver_row, text="约 4–5× 墙钟，八接触峰值偏差 ≤0.2%；派生算例写在输出目录的 "
                                          "case_used.json，原算例文件不动。",
                         style="Muted.TLabel", font=ui_font(theme.FONT_SIZE["micro"]),
                         justify="left")
        hint.pack(anchor="w", fill="x")
        self.wrap_with(hint, solver_row, reserve=8)
        pick_row = ttk.Frame(solver_row, style="Card.TFrame")
        pick_row.pack(fill="x", pady=(2, 0))
        ttk.Label(pick_row, text="方法", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left")
        self.method_var = tk.StringVar(value=self.METHOD_CHOICES[0])
        ttk.Combobox(pick_row, textvariable=self.method_var, values=list(self.METHOD_CHOICES),
                     state="readonly", width=13,
                     style="TCombobox").pack(side="left", padx=(theme.GAP, theme.PAD))
        ttk.Label(pick_row, text="雅可比", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left")
        self.jacobian_var = tk.StringVar(value=self.JACOBIAN_CHOICES[0])
        ttk.Combobox(pick_row, textvariable=self.jacobian_var,
                     values=list(self.JACOBIAN_CHOICES), state="readonly", width=12,
                     style="TCombobox").pack(side="left", padx=(theme.GAP, theme.PAD))
        ttk.Label(pick_row, text="rtol", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left")
        self.rtol_var = tk.StringVar(value="")
        ttk.Entry(pick_row, textvariable=self.rtol_var, width=9,
                  style="Field.TEntry").pack(side="left", padx=(theme.GAP, 0))

        actions = ttk.Frame(body, style="Card.TFrame")
        actions.grid(row=5, column=0, sticky="ew", pady=(theme.SPACE["2"], 0))
        actions.columnconfigure(0, weight=1, uniform="run-actions")
        actions.columnconfigure(1, weight=1, uniform="run-actions")
        self.start_button = ttk.Button(actions, text="启动单次运行", style="Primary.TButton",
                                       command=self.start_single)
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, theme.GAP))
        self.batch_button = ttk.Button(actions, text="批量运行", style="Ghost.TButton",
                                       command=self.start_batch)
        self.batch_button.grid(row=0, column=1, sticky="ew")
        self.cancel_button = ttk.Button(actions, text="取消", style="Danger.TButton",
                                        command=self.cancel, state="disabled")
        self.cancel_button.grid(row=1, column=0, sticky="ew", pady=(theme.GAP, 0),
                                padx=(0, theme.GAP))
        ttk.Button(actions, text="打开输出目录", style="Ghost.TButton",
                   command=self.open_output).grid(row=1, column=1, sticky="ew",
                                                  pady=(theme.GAP, 0))

        ttk.Label(body, text="命令行预览", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).grid(
            row=6, column=0, sticky="w", pady=(theme.SPACE["3"], 0))
        self.cmd_label = tk.Label(body, text="—", bg=theme.RAISED, fg=theme.INK_MUTED,
                                  font=(theme.FONT_MONO, theme.FONT_SIZE["micro"]),
                                  justify="left", anchor="w", padx=6, pady=4)
        self.cmd_label.grid(row=7, column=0, sticky="ew")
        self.wrap_with(self.cmd_label, body, reserve=16)

        # -- right: live log ---------------------------------------------
        right = Card(self, "实时输出")
        right.grid(row=0, column=1, sticky="nsew")
        rbody = right.body()
        metrics = ttk.Frame(rbody, style="Card.TFrame")
        metrics.pack(fill="x", pady=(0, theme.SPACE["2"]))
        self.card_state = MetricCard(metrics, "状态", "未启动", tone=theme.INK_MUTED)
        self.card_state.pack(side="left", padx=(0, theme.GAP))
        self.card_elapsed = MetricCard(metrics, "耗时", "—", "s")
        self.card_elapsed.pack(side="left", padx=(0, theme.GAP))
        self.card_lines = MetricCard(metrics, "输出行", "0")
        self.card_lines.pack(side="left", padx=(0, theme.GAP))
        self.card_code = MetricCard(metrics, "退出码", "—")
        self.card_code.pack(side="left", padx=(0, theme.GAP))
        ttk.Button(metrics, text="清空日志", style="Ghost.TButton",
                   command=self.clear_log).pack(side="right")

        log_frame = ttk.Frame(rbody, style="Card.TFrame")
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, bg=theme.BG, fg=theme.INK, insertbackground=theme.INK,
                           font=(theme.FONT_MONO, theme.FONT_SIZE["tiny"]), relief="flat",
                           highlightthickness=0, wrap="none", padx=theme.GAP, pady=6,
                           height=20, state="disabled")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        jump = ttk.Frame(rbody, style="Card.TFrame")
        jump.pack(fill="x", pady=(theme.SPACE["2"], 0))
        ttk.Button(jump, text="查看时程 →", style="Ghost.TButton",
                   command=lambda: self._goto("timeseries")).pack(side="left")
        ttk.Button(jump, text="查看评价 →", style="Ghost.TButton",
                   command=lambda: self._goto("assess")).pack(side="left", padx=(theme.GAP, 0))
        ttk.Button(jump, text="刷新运行目录", style="Ghost.TButton",
                   command=self.reload).pack(side="right")

    # -- data --------------------------------------------------------------
    def refresh(self) -> None:
        self.cases = store.scan_cases(hashing=False)
        self.case_list.clear()
        for index, info in enumerate(self.cases):
            self.case_list.tree.insert("", "end", iid=str(index),
                                       values=(info.case_id, info.duration_label, info.dof))
        self.set_rows(len(self.cases), f"{len(self.cases)} 个可选算例")
        if self.cases and not self.case_list.tree.selection():
            target = next((i for i, c in enumerate(self.cases)
                           if c.case_id == "A_final_law"), 0)
            self.case_list.tree.selection_set(str(target))
            self.case_list.tree.see(str(target))

    def on_context(self) -> None:
        case = self.app.context.get("case")
        if case is None or not self.cases:
            return
        for index, info in enumerate(self.cases):
            if info.path == Path(case):
                self.case_list.tree.selection_set(str(index))
                self.case_list.tree.see(str(index))
                break

    # -- selection helpers -------------------------------------------------
    def _selected(self) -> list[store.CaseInfo]:
        picked = []
        for iid in self.case_list.tree.selection():
            try:
                picked.append(self.cases[int(iid)])
            except (ValueError, IndexError):
                continue
        return picked

    def choose_dir(self) -> None:
        target = filedialog.askdirectory(parent=self, title="选择输出目录",
                                         initialdir=str(store.VALIDATION_DIR))
        if target:
            self.outdir_var.set(target)

    # -- launching ---------------------------------------------------------
    def _solver_flags(self) -> list[str]:
        """Translate the solver row into CLI flags; the case file is never rewritten."""

        flags: list[str] = []
        if self.fast_var.get():
            flags.append("--fast")
        method = self.METHOD_VALUES[self.METHOD_CHOICES.index(self.method_var.get())]
        if method:
            flags += ["--method", method]
        jacobian = self.JACOBIAN_VALUES[self.JACOBIAN_CHOICES.index(self.jacobian_var.get())]
        if jacobian:
            flags += ["--jacobian", jacobian]
        rtol = self.rtol_var.get().strip()
        if rtol:
            flags += ["--rtol", rtol]
        return flags

    def _argv_single(self, case: store.CaseInfo, outdir: Path) -> list[str]:
        return [sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle",
                str(case.path), "--output", str(outdir), *self._solver_flags()]


    def _argv_batch(self, cases: list[store.CaseInfo], root: Path) -> list[str]:
        argv = [sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle-batch"]
        argv += [str(case.path) for case in cases]
        argv += ["--output-root", str(root), "--jobs", str(max(1, int(self.jobs_var.get())))]
        return argv

    def start_single(self) -> None:
        picked = self._selected()
        if not picked:
            self.app.set_status("先选中一个算例", tone="warn")
            return
        case = picked[0]
        outdir = Path(self.outdir_var.get().strip() or
                      store.VALIDATION_DIR / f"out_ui_{case.case_id}")
        argv = self._argv_single(case, outdir)
        self._launch(argv, outdir, f"{case.case_id}")

    def start_batch(self) -> None:
        picked = self._selected()
        if not picked:
            self.app.set_status("批量运行至少选一个算例", tone="warn")
            return
        root = Path(self.outdir_var.get().strip() or
                    store.VALIDATION_DIR / "out_ui_batch")
        argv = self._argv_batch(picked, root)
        self._launch(argv, root, f"批量 ×{len(picked)}")

    def _launch(self, argv: list[str], outdir: Path, label: str) -> None:
        if self.app.process is not None and self.app.process.running:
            self.app.set_status("已有子进程在运行，先取消它", tone="warn")
            return
        self.clear_log()
        self.output_dir = outdir
        self.cmd_label.configure(text=" ".join(argv))
        self.card_state.set(label, tone=theme.AMBER)
        self.card_elapsed.set("0.0", "s")
        self.card_lines.set("0")
        self.card_code.set("—")
        self._append(f"$ {' '.join(argv)}")
        self._append(f"# cwd={store.REPO_ROOT}")
        if self.app.spawn(argv, store.REPO_ROOT, owner=self.name) is None:
            self._set_busy(False)
            return
        self._set_busy(True)
        self.app.set_status(f"已启动：{label}", tone="run")

    def _set_busy(self, busy: bool) -> None:
        """Only the cancel button is live while a child process owns the log."""

        state = "disabled" if busy else "normal"
        self.start_button.configure(state=state)
        self.batch_button.configure(state=state)
        self.cancel_button.configure(state="normal" if busy else "disabled")

    def cancel(self) -> None:
        self.app.cancel_job()

    def open_output(self) -> None:
        target = self.output_dir or Path(self.outdir_var.get().strip())
        if not target.exists():
            self.app.set_status(f"目录还不存在：{target}", tone="warn")
            return
        if sys.platform.startswith("win"):
            import os
            os.startfile(str(target))  # noqa: S606 - user asked to open the folder
        else:  # pragma: no cover - non-Windows fallback
            self.app.set_status(f"输出目录：{target}", tone="info")

    # -- log plumbing ------------------------------------------------------
    def _append(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log_lines += 1
        if self.log_lines > MAX_LOG_LINES:
            excess = self.log_lines - MAX_LOG_LINES
            self.log.delete("1.0", f"{excess + 1}.0")
            self.log_lines = MAX_LOG_LINES
        self.log.configure(state="disabled")
        if self.autoscroll_var.get():
            self.log.see("end")
        self.card_lines.set(str(self.log_lines))

    def clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.log_lines = 0
        self.card_lines.set("0")

    def on_log(self, line: str) -> None:
        self._append(line)
        if self.app.process is not None:
            self.card_elapsed.set(f"{self.app.process.elapsed:.1f}")

    def on_process_exit(self, code: int, elapsed: float, cancelled: bool) -> None:
        self._set_busy(False)
        self.card_elapsed.set(f"{elapsed:.1f}", "s")
        self.card_code.set(str(code), tone=theme.PASS if code == 0 else theme.FAIL)
        self.card_state.set("已取消" if cancelled else ("完成" if code == 0 else "失败"),
                            tone=theme.INK_MUTED if cancelled else
                            (theme.PASS if code == 0 else theme.FAIL))
        self._append(f"# 进程结束：退出码 {code}，用时 {elapsed:.1f} s"
                     + ("（已取消）" if cancelled else ""))
        if code == 0 and self.output_dir is not None:
            self.app.set_context(run=self.output_dir)
            self._append(f"# 结果目录：{self.output_dir}")
        self.reload()

    def _goto(self, screen: str) -> None:
        if self.output_dir is not None and self.output_dir.exists():
            self.app.set_context(run=self.output_dir)
        self.app.show(screen)

    def export_figure(self) -> None:
        self.app.set_status("运行屏没有图形可导出，日志可在此直接复制")
