"""发布证据：把 ``docs/EVIDENCE_MAP.md`` 原样放进一个窗口。

为什么不解析成结构化表格：那张表现在有六个分项、每项都带"跑出来的最近结果"，每次任务改动它的列。
重新实现的解析器只会成为第三份真相。这里显示**原文**，并标出文件的时间与大小——"哪一版"和
"写了什么"必须同时可见。
"""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from . import theme
from .widgets import ui_font

FILE_NAME = "EVIDENCE_MAP.md"

#: 重新生成这张表的命令；冻结版里没有 scripts/，所以只提示源码工作区。
REGENERATE = "python -X utf8 scripts/evidence_map.py --with-run"


def docs_roots() -> list[Path]:
    """可能放着 ``docs/`` 的目录：源码工作区、冻结版的安装目录与 ``_internal``。"""

    from ..selfcheck import docs_roots as _roots

    return list(_roots())


def locate_evidence_map() -> Path | None:
    """找到最新的那份 ``docs/EVIDENCE_MAP.md``；找不到返回 ``None``（不编一个空表）。"""

    found: list[Path] = []
    for root in docs_roots():
        candidate = root / "docs" / FILE_NAME
        if candidate.is_file():
            found.append(candidate)
    if not found:
        return None
    return max(found, key=lambda path: path.stat().st_mtime)


def describe(path: Path | None) -> str:
    """一行说明：路径 + 时间 + 大小；找不到时说清楚查过哪些地方。"""

    if path is None:
        looked = ", ".join(str(root / "docs" / FILE_NAME) for root in docs_roots())
        return f"未找到 {FILE_NAME}（查过：{looked}）；在源码工作区跑 {REGENERATE} 生成"
    stat = path.stat()
    when = dt.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    return f"{path}　·　{when}　·　{stat.st_size / 1024:.1f} KB"


class EvidenceMapDialog(tk.Toplevel):
    """只读窗口：原文 + 时间戳 + 一句话说明它能不能被信任。"""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("发布证据")
        self.configure(bg=theme.BG)
        self.geometry(f"{int(980 * theme.SCALE)}x{int(640 * theme.SCALE)}")
        self.transient(parent)

        self.path = locate_evidence_map()

        header = ttk.Frame(self, style="Bg.TFrame")
        header.pack(fill="x", padx=theme.PAD_LG, pady=(theme.PAD_LG, theme.SPACE["2"]))
        ttk.Label(header, text="发布证据（docs/EVIDENCE_MAP.md）",
                  style="Section.TLabel").pack(anchor="w")
        self.where = ttk.Label(header, text=describe(self.path), style="Dim.TLabel",
                               justify="left", font=ui_font(theme.FONT_SIZE["micro"]))
        self.where.pack(anchor="w", pady=(theme.SPACE["1"], 0))
        # Screen 才有 wrap_with；Toplevel 里就地绑一次，跟随窗口宽度换行。
        header.bind("<Configure>",
                    lambda event: self.where.configure(
                        wraplength=max(240, event.width - 16)), add="+")

        body = ttk.Frame(self, style="Bg.TFrame")
        body.pack(fill="both", expand=True, padx=theme.PAD_LG)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.text = tk.Text(body, wrap="word", bg=theme.SURFACE, fg=theme.INK,
                            insertbackground=theme.INK, relief="flat",
                            padx=theme.SPACE["3"], pady=theme.SPACE["3"],
                            font=ui_font(theme.FONT_SIZE["micro"]), height=24)
        self.text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scroll.set)
        self.text.tag_configure("heading", foreground=theme.INK, font=ui_font(theme.FONT_SIZE["body"]))
        self.text.tag_configure("good", foreground=theme.PASS)
        self.text.tag_configure("plain", foreground=theme.INK_MUTED)

        footer = ttk.Frame(self, style="Bg.TFrame")
        footer.pack(fill="x", padx=theme.PAD_LG, pady=theme.PAD_LG)
        ttk.Label(footer, text=f"重新生成：{REGENERATE}", style="Dim.TLabel",
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left")
        ttk.Button(footer, text="关闭", style="Ghost.TButton",
                   command=self.destroy).pack(side="right")

        self.fill()

    def fill(self) -> None:
        self.text.configure(state="normal")
        if self.path is None:
            self.text.insert("end", describe(None) + "\n", "plain")
        else:
            for line in self.path.read_text(encoding="utf-8").splitlines(keepends=True):
                if line.startswith("#"):
                    self.text.insert("end", line, "heading")
                elif "ACCEPT" in line or "UNCHANGED" in line or "通过" in line:
                    self.text.insert("end", line, "good")
                else:
                    self.text.insert("end", line, "plain")
        self.text.configure(state="disabled")


def show_evidence_map_dialog(parent: tk.Misc) -> EvidenceMapDialog:
    dialog = EvidenceMapDialog(parent)
    dialog.update_idletasks()
    dialog.lift()
    return dialog
