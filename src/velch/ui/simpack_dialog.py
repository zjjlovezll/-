"""Derive a Velch case from a Simpack model, from inside the interface.

The interface must not import the forward stack, and a frozen build has no ``-X utf8 -m velch``
to run either — so this dialog builds the same command line the user would type, runs it through
:mod:`velch.launcher`, and shows what the command said.  The command is the contract: if the dialog
can do something the CLI cannot, one of them is lying.
"""
from __future__ import annotations

import json
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from . import theme
from .widgets import ui_font
from ..launcher import launcher_argv


class SimpackImportDialog(tk.Toplevel):
    """Modal dialog: pick a catalog, a template and a window; the CLI does the work."""

    def __init__(self, master: tk.Misc, *, template: Path | None, case_dir: Path,
                 on_done=None) -> None:
        super().__init__(master)
        self.title("从 Simpack 模型派生算例")
        self.configure(bg=theme.BG)
        self._case_dir = case_dir
        self._on_done = on_done
        self.report: dict | None = None
        self.command: list[str] = []

        self.catalog = tk.StringVar()
        self.template = tk.StringVar(value=str(template) if template else "")
        self.case_id = tk.StringVar(value=f"simpack_{Path(str(template or 'case')).stem}")
        self.x_start = tk.StringVar(value="60")
        self.duration = tk.StringVar(value="0.05")
        self.sample = tk.StringVar(value="60")
        self.side = tk.StringVar(value="right")
        self.rail = tk.StringVar(value="")
        self.keep_profiles = tk.BooleanVar(value=False)
        self.seat_check = tk.BooleanVar(value=True)

        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close())
        try:
            self.transient(master.winfo_toplevel())
            self.grab_set()
        except tk.TclError:  # pragma: no cover - headless or already destroyed
            pass

    # -- layout ------------------------------------------------------------

    def _build(self) -> None:
        body = ttk.Frame(self, style="Bg.TFrame", padding=theme.PAD_LG)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        ttk.Label(body, text="Simpack 模型只提供钢轨几何；质量、刚度、接触参数一律来自模板算例。",
                  style="Muted.TLabel", font=ui_font(theme.FONT_SIZE["body"]),
                  justify="left").grid(row=0, column=0, columnspan=3, sticky="w",
                                       pady=(0, theme.GAP))

        row = 1
        for caption, var, hint, browse in (
                ("断面目录 JSON", self.catalog,
                 "先跑 inspect-simpack-track 生成的 catalog.json", self._browse_catalog),
                ("模板算例", self.template,
                 "质量 / 刚度 / 接触参数取自这个算例", self._browse_template)):
            ttk.Label(body, text=caption, style="Muted.TLabel",
                      font=ui_font(theme.FONT_SIZE["body"])).grid(row=row, column=0, sticky="w",
                                                                   pady=2)
            ttk.Entry(body, textvariable=var, style="Field.TEntry").grid(row=row, column=1,
                                                                        sticky="ew", pady=2)
            ttk.Button(body, text="选择…", style="Ghost.TButton", command=browse).grid(
                row=row, column=2, sticky="ew", padx=(theme.GAP, 0), pady=2)
            row += 1
            ttk.Label(body, text=hint, style="Dim.TLabel",
                      font=ui_font(theme.FONT_SIZE["micro"])).grid(row=row, column=1, sticky="w")
            row += 1

        numbers = ttk.Frame(body, style="Bg.TFrame")
        numbers.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(theme.GAP, 0))
        for column, (caption, var, width) in enumerate((
                ("新算例 ID", self.case_id, 20),
                ("起点 m", self.x_start, 7),
                ("时长 s", self.duration, 7),
                ("采样站数", self.sample, 7))):
            ttk.Label(numbers, text=caption, style="Muted.TLabel",
                      font=ui_font(theme.FONT_SIZE["micro"])).grid(row=0, column=column * 2,
                                                                    sticky="e",
                                                                    padx=(0 if column == 0 else theme.GAP,
                                                                          4))
            ttk.Entry(numbers, textvariable=var, style="Field.TEntry", width=width).grid(
                row=0, column=column * 2 + 1, sticky="ew")
        numbers.columnconfigure(1, weight=1)
        row += 1

        options = ttk.Frame(body, style="Bg.TFrame")
        options.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(theme.GAP, 0))
        ttk.Label(options, text="侧别", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left")
        ttk.Combobox(options, textvariable=self.side, values=("right", "left"), width=7,
                     state="readonly").pack(side="left", padx=(4, theme.GAP))
        ttk.Label(options, text="轨别", style="Muted.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left")
        ttk.Entry(options, textvariable=self.rail, style="Field.TEntry", width=10).pack(
            side="left", padx=(4, theme.GAP))
        ttk.Checkbutton(options, text="型面沿用模板", variable=self.keep_profiles).pack(
            side="left", padx=(0, theme.GAP))
        ttk.Checkbutton(options, text="派生后裁决", variable=self.seat_check).pack(side="left")
        row += 1

        actions = ttk.Frame(body, style="Bg.TFrame")
        actions.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(theme.GAP, 0))
        self.derive_button = ttk.Button(actions, text="生成算例", style="Primary.TButton",
                                        command=self.derive)
        self.derive_button.pack(side="left")
        ttk.Button(actions, text="关闭", style="Ghost.TButton", command=self.close).pack(
            side="left", padx=(theme.GAP, 0))
        self.status = ttk.Label(actions, text="", style="Muted.TLabel",
                                font=ui_font(theme.FONT_SIZE["micro"]))
        self.status.pack(side="left", padx=(theme.GAP, 0))
        row += 1

        self.output = tk.Text(body, height=11, wrap="none", bg=theme.SURFACE, fg=theme.INK,
                              insertbackground=theme.INK, relief="flat",
                              font=(theme.FONT_MONO, theme.FONT_SIZE["micro"]))
        self.output.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=(theme.GAP, 0))
        body.rowconfigure(row, weight=1)
        self.geometry(f"{int(780 * theme.SCALE)}x{int(540 * theme.SCALE)}")

    # -- actions -----------------------------------------------------------

    def _browse_catalog(self) -> None:
        name = filedialog.askopenfilename(parent=self, title="选择 Simpack 断面目录 JSON",
                                          filetypes=(("JSON", "*.json"), ("所有文件", "*.*")))
        if name:
            self.catalog.set(name)

    def _browse_template(self) -> None:
        name = filedialog.askopenfilename(parent=self, title="选择模板算例",
                                          initialdir=str(self._case_dir),
                                          filetypes=(("算例", "case_*.json"), ("所有文件", "*.*")))
        if name:
            self.template.set(name)

    def output_path(self) -> Path:
        name = self.case_id.get().strip() or "simpack_case"
        return self._case_dir / f"{name}.json"

    def build_command(self) -> list[str]:
        if not self.catalog.get().strip():
            raise ValueError("先选一个断面目录 JSON（catalog.json）")
        if not self.template.get().strip():
            raise ValueError("先选一个模板算例")
        argv = ["simpack-case",
                "--catalog", self.catalog.get().strip(),
                "--template", self.template.get().strip(),
                "--out", str(self.output_path()),
                "--x-start", self.x_start.get().strip(),
                "--duration", self.duration.get().strip(),
                "--side", self.side.get(),
                "--case-id", self.case_id.get().strip() or "simpack_case"]
        sample = self.sample.get().strip()
        if sample:
            argv += ["--sample", sample]
        rail = self.rail.get().strip()
        if rail:
            argv += ["--rail", rail]
        if self.keep_profiles.get():
            argv.append("--keep-profiles")
        if not self.seat_check.get():
            argv.append("--no-seat-check")
        return launcher_argv(*argv)

    def derive(self) -> None:
        try:
            command = self.build_command()
        except ValueError as error:
            self.status.configure(text=str(error))
            return
        self.command = command
        self.derive_button.state(["disabled"])
        self.status.configure(text="正在生成…")
        self.update_idletasks()
        code, text = self._run(command)
        self.output.delete("1.0", "end")
        self.output.insert("end", text.strip())
        self.report = _parse_report(text)
        self.status.configure(text=_status_line(code, self.report))
        self.derive_button.state(["!disabled"])
        if self._on_done is not None and code == 0:
            self._on_done(self.output_path())

    def _run(self, command: list[str]) -> tuple[int, str]:
        try:
            done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=900)
        except (OSError, subprocess.SubprocessError) as error:
            return -1, f"{type(error).__name__}: {error}"
        return done.returncode, (done.stdout or "") + (done.stderr or "")

    def close(self) -> None:
        try:
            self.grab_release()
        finally:
            self.destroy()


def _parse_report(text: str) -> dict | None:
    """The CLI prints one JSON object; find it without assuming it is the whole output."""
    start = text.find("{")
    while start != -1:
        try:
            return json.loads(text[start:])
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
    return None


def _status_line(code: int, report: dict | None) -> str:
    if report is None:
        return f"命令退出码 {code}，没读懂它的输出"
    seating = report.get("seating")
    if seating is None:
        return "已生成算例（未跑静平衡裁决）"
    if seating.get("seats"):
        return f"静平衡坐住了（残差 {seating.get('residual_n') or 0.0:.2e} N）"
    return "静平衡没坐住：这段里程下没有承载面，见输出里的建议"


def show_simpack_dialog(master: tk.Misc, *, template: Path | None, case_dir: Path,
                        on_done=None) -> SimpackImportDialog:
    return SimpackImportDialog(master, template=template, case_dir=case_dir, on_done=on_done)
