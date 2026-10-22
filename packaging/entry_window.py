"""Windowed entry point of the packaged product (``Velch.exe``).

No console: the Tk window is the whole interface.  A crash before the window exists must not look
like "nothing happened", so an unexpected exception is shown in a message box with the traceback
and written next to the executable -- a windowed build otherwise dies silently.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path


def _report(crash: BaseException) -> None:
    detail = "".join(traceback.format_exception(type(crash), crash, crash.__traceback__))
    try:
        log = Path(sys.executable).with_name("velch-crash.log")
        log.write_text(detail, encoding="utf-8", newline="\n")
    except OSError:
        log = None
    try:
        import tkinter.messagebox as box
        box.showerror("Velch 未能启动",
                      f"{type(crash).__name__}: {crash}\n\n"
                      + (f"详细堆栈已写入：\n{log}" if log else detail[-1200:]))
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    try:
        from velch.ui import main as ui_main
        return int(ui_main(list(sys.argv[1:] if argv is None else argv)))
    except SystemExit:
        raise
    except BaseException as crash:  # noqa: BLE001 - the point is to survive a bad start
        _report(crash)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
