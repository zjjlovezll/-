"""Screen ①「算例」: browse, inspect and derive the case library.

Left is a filterable table of every ``validation/crh380a_m/case_*.json``; right is the
selected case's contract (schema, duration, DOF, start station, output step, SHA-256) and
the derive form.  Deriving writes a **new JSON file** next to the source with a new
``case_id`` and optional ``run.duration_s`` / ``run.output_step_s`` overrides — the UI
never edits an existing case in place and never touches numerical code.
"""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from . import store, theme
from .screen import Screen
from .widgets import Card, ListPanel, ui_font

COLUMNS = (
    ("case_id", "算例 ID", 240),
    ("duration", "时长", 76),
    ("dof", "自由度", 66),
    ("xstart", "起始里程 m", 96),
    ("step", "输出步长 s", 92),
    ("sha", "资产哈希", 116),
)
DEFAULT_FILTER_HINT = "按 ID / 目的 / 自由度 过滤，例如 frog 或 35"


class CasesScreen(Screen):
    name = "cases"
    title = "算例库"
    subtitle = "列出 validation/crh380a_m 下的算例，检视自由度与资产哈希，可复制派生"

    def _build(self) -> None:
        self.infos: list[store.CaseInfo] = []
        self.visible: list[store.CaseInfo] = []
        self.selected: store.CaseInfo | None = None
        self.filter_var = tk.StringVar()

        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=4)
        self.rowconfigure(1, weight=1)

        overview = ttk.Frame(self, style="Bg.TFrame")
        overview.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, theme.SPACE["3"]))
        self.chip_total = None  # created after the first load
        self.overview_row = ttk.Frame(overview, style="Bg.TFrame")
        self.overview_row.pack(anchor="w")

        # -- left: table -------------------------------------------------
        left = Card(self, "算例清单")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, theme.SPACE["3"]))
        body = left.body()
        search_row = ttk.Frame(body, style="Card.TFrame")
        search_row.pack(fill="x", pady=(0, theme.SPACE["2"]))
        ttk.Label(search_row, text="筛选", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left")
        self.filter_entry = ttk.Entry(search_row, textvariable=self.filter_var,
                                      style="Field.TEntry")
        self.filter_entry.pack(side="left", fill="x", expand=True, padx=(theme.GAP, 0))
        self.filter_var.trace_add("write", lambda *_a: self._apply_filter())
        self.table = ListPanel(body, height=18)
        self.table.pack(fill="both", expand=True)
        self.table.columns(COLUMNS)
        self.table.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.table.tree.bind("<Double-1>", lambda _e: self.open_in_run())

        # -- right: detail + derive --------------------------------------
        right = Card(self, "算例契约")
        right.grid(row=1, column=1, sticky="nsew")
        detail = right.body()
        self.fields: dict[str, ttk.Label] = {}
        grid = ttk.Frame(detail, style="Card.TFrame")
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)
        spec = (("case_id", "算例编号"), ("schema", "算例格式"),
                ("purpose", "目的"), ("duration", "时长"),
                ("dof", "自由度"), ("x_start", "起始里程"),
                ("step", "输出步长"), ("size", "文件大小"),
                ("sha", "文件哈希（SHA-256）"), ("path", "文件路径"))
        for row, (key, label) in enumerate(spec):
            ttk.Label(grid, text=label, style="Dim.TLabel",
                      font=ui_font(theme.FONT_SIZE["micro"])).grid(
                row=row, column=0, sticky="w", pady=1, padx=(0, theme.SPACE["3"]))
            value = tk.Label(grid, text="—", bg=theme.SURFACE, fg=theme.INK,
                             font=(theme.FONT_MONO, theme.FONT_SIZE["micro"]),
                             anchor="w", justify="left", wraplength=420)
            value.grid(row=row, column=1, sticky="w", pady=1)
            self.fields[key] = value

        ttk.Separator(detail).pack(fill="x", pady=theme.SPACE["4"])
        ttk.Label(detail, text="复制派生", style="Section.TLabel").pack(anchor="w")
        ttk.Label(detail, text="派生只写出一个新的 case_*.json；原算例与数值代码保持不变。",
                  style="Dim.TLabel", font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")

        self.derive_id = tk.StringVar()
        self.derive_duration = tk.StringVar()
        self.derive_step = tk.StringVar()
        form = ttk.Frame(detail, style="Card.TFrame")
        form.pack(fill="x", pady=theme.SPACE["2"])
        form.columnconfigure(1, weight=1)
        for row, (label, var, hint) in enumerate((
                ("新算例 ID", self.derive_id, "留空则用 <原名>_ui"),
                ("时长覆盖 s", self.derive_duration, "留空沿用原值"),
                ("步长覆盖 s", self.derive_step, "留空沿用原值"))):
            ttk.Label(form, text=label, style="Muted.TLabel",
                      font=ui_font(theme.FONT_SIZE["micro"])).grid(
                row=row, column=0, sticky="w", padx=(0, theme.SPACE["2"]), pady=1)
            ttk.Entry(form, textvariable=var, style="Field.TEntry").grid(
                row=row, column=1, sticky="ew", pady=1)
            ttk.Label(form, text=hint, style="Dim.TLabel",
                      font=ui_font(theme.FONT_SIZE["micro"])).grid(row=row, column=2,
                                                                   sticky="w",
                                                                   padx=(theme.GAP, 0))

        actions = ttk.Frame(detail, style="Card.TFrame")
        actions.pack(fill="x", pady=(theme.SPACE["2"], 0))
        ttk.Button(actions, text="派生新算例", style="Primary.TButton",
                   command=self.derive_case).pack(side="left")
        ttk.Button(actions, text="复制路径", style="Ghost.TButton",
                   command=lambda: self._copy(self.selected.path if self.selected else "",
                                              "已复制算例路径")).pack(side="left",
                                                                      padx=(theme.GAP, 0))
        ttk.Button(actions, text="复制命令", style="Ghost.TButton",
                   command=self.copy_command).pack(side="left", padx=(theme.GAP, 0))

        nav = ttk.Frame(detail, style="Card.TFrame")
        nav.pack(fill="x", pady=(theme.SPACE["1"], 0))
        ttk.Button(nav, text="在「运行」屏打开", style="Ghost.TButton",
                   command=self.open_in_run).pack(side="left")
        ttk.Button(nav, text="刷新列表", style="Ghost.TButton",
                   command=self.reload).pack(side="left", padx=(theme.GAP, 0))

        self.result_label = ttk.Label(detail, text="", style="Muted.TLabel",
                                      wraplength=560, justify="left")
        self.result_label.pack(anchor="w", pady=(theme.SPACE["3"], 0))

    # -- data --------------------------------------------------------------
    def refresh(self) -> None:
        self.infos = store.scan_cases()
        self.visible = list(self.infos)
        self._fill_table()
        self._fill_overview()
        faults = [info for info in self.infos if info.problem]
        detail = (f"{len(self.infos)} 个算例 · {sum(i.size_bytes for i in self.infos)/1024/1024:.1f} MB"
                  f" · 含故障 {len(faults)}")
        self.set_rows(len(self.infos), detail)

    def _fill_overview(self) -> None:
        for child in self.overview_row.winfo_children():
            child.destroy()
        from .widgets import Chip
        dofs: dict[int, int] = {}
        for info in self.infos:
            dofs[info.dof] = dofs.get(info.dof, 0) + 1
        dof_text = " · ".join(f"{dof} 自由度 ×{count}"
                              for dof, count in sorted(dofs.items()))
        for text, tone in ((f"{len(self.infos)} 个算例", "info"),
                           (f"总大小 {sum(i.size_bytes for i in self.infos)/1024/1024:.1f} MB",
                            "idle"),
                           (dof_text, "idle"),
                           (store.VALIDATION_DIR.name, "accent")):
            chip = Chip(self.overview_row, text, tone)
            chip.pack(side="left", padx=(0, theme.GAP))

    def _fill_table(self) -> None:
        self.table.clear()
        for index, info in enumerate(self.visible):
            values = (info.case_id, info.duration_label, info.dof or "—",
                      "—" if info.x_start_m is None else f"{info.x_start_m:.2f}",
                      "—" if info.output_step_s is None else f"{info.output_step_s:g}",
                      info.sha_short)
            tags = ("bad",) if info.problem else ()
            self.table.tree.insert("", "end", iid=str(index), values=values, tags=tags)
        self.table.tree.tag_configure("bad", foreground=theme.FAIL)
        self.set_rows(len(self.visible), f"{len(self.visible)}/{len(self.infos)} 个算例列在表中")

    def _apply_filter(self) -> None:
        needle = self.filter_var.get().strip().lower()
        if not needle:
            self.visible = list(self.infos)
        else:
            self.visible = [info for info in self.infos
                            if needle in info.case_id.lower()
                            or needle in info.purpose.lower()
                            or needle in str(info.dof)]
        self._fill_table()

    # -- interaction -------------------------------------------------------
    def _on_select(self, _event=None) -> None:
        selection = self.table.tree.selection()
        if not selection:
            return
        index = int(selection[0])
        if not (0 <= index < len(self.visible)):
            return
        self.selected = self.visible[index]
        info = self.selected
        self.fields["case_id"].configure(text=info.case_id)
        self.fields["schema"].configure(text=info.schema or "（未声明）")
        self.fields["purpose"].configure(text=info.purpose or "—")
        self.fields["duration"].configure(text=f"{info.duration_label}"
                                               + (f" · 输出步长已设" if info.output_step_s else ""))
        self.fields["dof"].configure(text=f"{info.dof} 个广义坐标")
        self.fields["x_start"].configure(text="—" if info.x_start_m is None
                                         else f"{info.x_start_m:.3f} m")
        self.fields["step"].configure(text="—" if info.output_step_s is None
                                      else f"{info.output_step_s:g} s")
        self.fields["size"].configure(text=f"{info.size_bytes/1024:.1f} KiB")
        self.fields["sha"].configure(text=info.sha256 or "—")
        self.fields["path"].configure(text=str(info.path))
        self.derive_id.set(f"{info.case_id}_ui")
        self.derive_duration.set("" if info.duration_s is None else f"{info.duration_s:g}")
        self.derive_step.set("" if info.output_step_s is None else f"{info.output_step_s:g}")
        self.result_label.configure(text=("该算例存在读取问题：" + info.problem)
                                    if info.problem else "")
        self.app.set_context(case=info.path)

    def open_in_run(self) -> None:
        if self.selected is None:
            self.app.set_status("先选中一个算例", tone="warn")
            return
        self.app.set_context(case=self.selected.path)
        self.app.show("run")

    def copy_command(self) -> None:
        if self.selected is None:
            self.app.set_status("先选中一个算例", tone="warn")
            return
        info = self.selected
        out = store.VALIDATION_DIR / f"out_{info.case_id}_ui"
        command = (f'python -X utf8 -m velch run-vehicle "{info.path}" '
                   f'--output "{out}"')
        self._copy(command, "已复制 CLI 命令")

    def _copy(self, text: object, status: str) -> None:
        if not text:
            self.app.set_status("没有可复制的内容", tone="warn")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(str(text))
        self.app.set_status(status, tone="pass")

    def derive_case(self) -> None:
        if self.selected is None:
            self.app.set_status("先选中一个算例", tone="warn")
            return
        info = self.selected
        if info.problem:
            self.app.set_status("该算例无法解析，不能派生", tone="fail")
            return
        try:
            payload = json.loads(info.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.app.set_status(f"派生失败：{exc}", tone="fail")
            return
        payload["case_id"] = (self.derive_id.get().strip() or f"{info.case_id}_ui")
        run = payload.get("run")
        if isinstance(run, dict):
            for key, var in (("duration_s", self.derive_duration),
                             ("output_step_s", self.derive_step)):
                raw = var.get().strip()
                if not raw:
                    continue
                try:
                    run[key] = float(raw)
                except ValueError:
                    self.app.set_status(f"{key} 不是数字：{raw}", tone="fail")
                    return
        target = filedialog.asksaveasfilename(
            parent=self, title="派生算例另存为",
            initialdir=str(info.path.parent), initialfile=f"case_{payload['case_id']}.json",
            defaultextension=".json", filetypes=[("Velch 算例", "*.json")])
        if not target:
            self.app.set_status("已取消派生")
            return
        path = Path(target)
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        except OSError as exc:
            self.app.set_status(f"派生写入失败：{exc}", tone="fail")
            return
        digest = store.file_sha256(path)
        self.result_label.configure(
            text=f"已派生：{path.name}\ncase_id = {payload['case_id']}\nsha256 = {digest}")
        self.app.set_status(f"派生成功 · {path.name}", tone="pass")
        self.reload()

    def export_figure(self) -> None:
        self.app.set_status("算例屏没有图形可导出")
