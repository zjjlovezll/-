"""要一个窗口，把"还差什么"和"已通过什么"摆在同一个地方。

数据在 :mod:`velch.open_items`（程序可读的那一份），`docs/BUGS.md` 是给人读的那一份；两者的
一致性由 `tests/test_open_items.py` 双向守着，所以这里不解析 markdown——解析器会成为第三份真相。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..open_items import ITEMS, LEDGER, OpenItem, by_id, counts
from . import theme
from .widgets import ui_font

#: 状态 → (中文标签, 颜色)  —— 颜色只在"要动"的条目上抢眼，设计约束与已关闭用静色。
STATUS: dict[str, tuple[str, str]] = {
    "open": ("待修", theme.FAIL),
    "by_design": ("设计约束", theme.WARN),
    "closed": ("已关闭", theme.INK_DIM),
}


def outline() -> list[str]:
    """纯文本大纲（无 Tk），供测试与 `--json` 复用。"""
    tally = counts()
    lines = [
        f"已知未修 {tally['open']} 项 · 设计约束 {tally['by_design']} 项 · 已关闭 {tally['closed']} 项",
        f"人读的账本：{LEDGER}",
        "",
    ]
    for item in ITEMS:
        label, _ = STATUS[item.status]
        lines.append(f"[{item.id}] {label}　{item.title}")
        lines.append(f"    {item.why}")
        if item.since:
            lines.append(f"    记录于 {item.since}")
        lines.append("")
    return lines


def _label_for(item: OpenItem) -> str:
    label, _ = STATUS[item.status]
    return f"[{item.id}] {label}"


class OpenItemsDialog(tk.Toplevel):
    """只读窗口：每条已知未修项一行标题 + 一段解释。"""

    WIDTH = 980
    HEIGHT = 620

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title("Velch · 已知问题")
        self.configure(bg=theme.BG)
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(int(self.WIDTH * 0.7), int(self.HEIGHT * 0.6))

        tally = counts()
        header = ttk.Label(
            self,
            text=(f"已知未修 {tally['open']} 项，另有 {tally['by_design']} 项是设计约束。"
                  f"人读的完整账本在 {LEDGER}（含已关闭与撤销的理由）。"),
            style="Muted.TLabel", justify="left",
        )
        header.pack(fill="x", padx=theme.SPACE["4"], pady=(theme.SPACE["3"], theme.SPACE["2"]))
        header.bind("<Configure>",
                    lambda event: header.configure(wraplength=max(320, event.width - 8)))

        body = ttk.Frame(self, style="Bg.TFrame")
        body.pack(fill="both", expand=True, padx=theme.SPACE["4"], pady=(0, theme.SPACE["4"]))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.text = tk.Text(body, wrap="word", height=18, relief="flat", borderwidth=0,
                            bg=theme.SURFACE, fg=theme.INK, insertwidth=0,
                            font=ui_font(theme.FONT_SIZE["body"]),
                            padx=theme.SPACE["3"], pady=theme.SPACE["2"],
                            spacing1=2, spacing3=6)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        self.text.tag_configure("open", foreground=theme.FAIL,
                                font=ui_font(theme.FONT_SIZE["body_lg"]))
        self.text.tag_configure("by_design", foreground=theme.WARN,
                                font=ui_font(theme.FONT_SIZE["body_lg"]))
        self.text.tag_configure("closed", foreground=theme.INK_DIM,
                                font=ui_font(theme.FONT_SIZE["body_lg"]))
        self.text.tag_configure("why", foreground=theme.INK_MUTED,
                                lmargin1=int(24 * theme.SCALE), lmargin2=int(24 * theme.SCALE))
        self.text.tag_configure("since", foreground=theme.INK_DIM,
                                lmargin1=int(24 * theme.SCALE))

        for item in ITEMS:
            self.text.insert("end", f"{_label_for(item)}　{item.title}\n", item.status)
            self.text.insert("end", f"{item.why}\n", "why")
            if item.since:
                self.text.insert("end", f"记录于 {item.since}\n", "since")
            self.text.insert("end", "\n")
        self.text.configure(state="disabled")

        footer = ttk.Frame(self, style="Bg.TFrame")
        footer.pack(fill="x", padx=theme.SPACE["4"], pady=(0, theme.SPACE["3"]))
        ttk.Button(footer, text="关闭", style="Ghost.TButton",
                   command=self.destroy).pack(side="right")


def show_open_items(master: tk.Misc) -> OpenItemsDialog:
    dialog = OpenItemsDialog(master)
    dialog.transient(master.winfo_toplevel())
    dialog.lift()
    return dialog
