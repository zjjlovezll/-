"""环境体检：在界面里跑一次 ``velch selfcheck``，把结果原样给人看。

为什么是子进程：体检要读语料、试 Tk、试 matplotlib、试 Simpack 路径、试可写目录——这些都在
``velch.selfcheck`` 里，而界面不 import 前向求解栈之外的东西也不该 import 自检（冻结包里
``Velch.exe`` 与 ``velch-cli.exe`` 是同一个入口的两张面孔）。走 ``launcher.launcher_argv``
保证源码版与冻结版走同一条路。
"""

from __future__ import annotations

import subprocess
import tkinter as tk
from tkinter import ttk

from ..launcher import launcher_argv
from . import theme
from .widgets import ui_font

#: 体检最长等多久。它是本机检查（读目录、试 import），不该超过几秒。
TIMEOUT_S = 60.0


class SelfCheckDialog(tk.Toplevel):
    """显示 ``velch selfcheck`` 的原始输出，并把 FAIL 行标红、WARN 行标黄。"""

    def __init__(self, parent: tk.Misc, *, run_dir: str | None = None) -> None:
        super().__init__(parent)
        self.title("环境体检")
        self.configure(bg=theme.BG)
        self.geometry(f"{int(880 * theme.SCALE)}x{int(560 * theme.SCALE)}")
        self.transient(parent)

        header = ttk.Frame(self, style="Bg.TFrame")
        header.pack(fill="x", padx=theme.PAD_LG, pady=(theme.PAD_LG, theme.SPACE["2"]))
        ttk.Label(header, text="环境体检（velch selfcheck）", style="Section.TLabel").pack(anchor="w")
        ttk.Label(header, style="Dim.TLabel", justify="left",
                  text="检查版本说明、算例语料、Tk、matplotlib、Simpack 路径与可写目录；"
                       "FAIL 项带一句可执行的修法。").pack(anchor="w", pady=(theme.SPACE["1"], 0))

        body = ttk.Frame(self, style="Bg.TFrame")
        body.pack(fill="both", expand=True, padx=theme.PAD_LG)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.text = tk.Text(body, wrap="word", bg=theme.SURFACE, fg=theme.INK,
                            insertbackground=theme.INK, relief="flat", padx=theme.SPACE["3"],
                            pady=theme.SPACE["3"], font=ui_font(theme.FONT_SIZE["micro"]),
                            height=20)
        self.text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scroll.set)
        self.text.tag_configure("fail", foreground=theme.FAIL)
        self.text.tag_configure("warn", foreground=theme.WARN)
        self.text.tag_configure("pass", foreground=theme.INK_MUTED)
        run_dir = run_dir or str(_launch_dir())
        self.text.insert("end", f"$ {run_dir} selfcheck\n\n", "pass")
        self.text.configure(state="disabled")

        footer = ttk.Frame(self, style="Bg.TFrame")
        footer.pack(fill="x", padx=theme.PAD_LG, pady=theme.PAD_LG)
        self.summary = tk.StringVar(value="正在检查…")
        ttk.Label(footer, textvariable=self.summary, style="Muted.TLabel").pack(side="left")
        ttk.Button(footer, text="关闭", style="Ghost.TButton",
                   command=self.destroy).pack(side="right")

    def run(self) -> int:
        """跑一次体检并把输出贴进来；返回退出码（0 = 全 PASS）。"""

        command = launcher_argv("selfcheck")
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
        except (OSError, subprocess.SubprocessError) as error:
            self._append(f"无法启动体检：{type(error).__name__}: {error}\n", "fail")
            self.summary.set("体检没跑起来")
            return 2
        text = (completed.stdout or "") + (completed.stderr or "")
        warnings = 0
        failures = 0
        for line in text.splitlines(keepends=True):
            stripped = line.lstrip()
            if stripped.startswith("[FAIL]"):
                self._append(line, "fail")
                failures += 1
            elif stripped.startswith("[WARN]"):
                self._append(line, "warn")
                warnings += 1
            elif stripped.startswith("[PASS]"):
                self._append(line, "pass")
            else:
                self._append(line, None)
        # 「全部通过」和「通过但有提示」不是同一句话：WARN 退 0，但它确实在说某个能力没开。
        if completed.returncode != 0 or failures:
            self.summary.set(f"体检完成：{failures} 项需要处理")
        elif warnings:
            self.summary.set(f"体检完成：可用，有 {warnings} 项提示")
        else:
            self.summary.set("体检完成：全部通过")
        self.text.see("end")
        return completed.returncode

    def _append(self, chunk: str, tag: str | None) -> None:
        self.text.configure(state="normal")
        if tag:
            self.text.insert("end", chunk, tag)
        else:
            self.text.insert("end", chunk)
        self.text.configure(state="disabled")


def _launch_dir():
    from ..data_root import frozen_install_root, is_frozen, repository_root

    return frozen_install_root() if is_frozen() else repository_root()


def show_selfcheck_dialog(parent: tk.Misc, *, run_dir: str | None = None) -> SelfCheckDialog:
    """打开对话框并**立刻**跑体检（打开它是用户已经表达了意图）。"""

    dialog = SelfCheckDialog(parent, run_dir=run_dir)
    dialog.update_idletasks()
    dialog.lift()
    dialog.run()
    return dialog
