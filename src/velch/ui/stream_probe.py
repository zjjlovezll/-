"""A child process that prints three log lines then exits 0.

The UI self-test uses it to prove the stdout pipe is wired (not just that a subprocess can start).
Kept in this module so the argv is built in exactly one place -- the earlier inline
``[sys.executable, "-X", "utf8", "-c", ...]`` broke a frozen build, because a packaged exe is not
a Python interpreter that accepts ``-c``.

A frozen build must also spawn the *console* sibling (``velch-cli.exe``), not the windowed exe it
is running inside: the windowed entry point owns the Tk app and rejects ``--selftest-stream``
(that mistake showed up in the first packaged smoke test as "usage: python -X utf8 -m velch.ui",
exit code 2, zero log lines).
"""
from __future__ import annotations

import sys
from pathlib import Path

STREAM_PROBE = ("import sys\n"
                "for line in ('velch-ui-stream-ok', 'second line', 'third line'):\n"
                "    print(line, flush=True)\n"
                "sys.exit(0)\n")


def stream_probe_argv() -> list[str]:
    """Argv for the stream probe, valid from source and from a frozen build."""

    from ..launcher import console_executable, is_frozen
    if is_frozen():
        executable = console_executable()
        console_like = "cli" in Path(executable).stem.lower()
        if Path(executable).resolve() == Path(sys.executable).resolve() and not console_like:
            raise RuntimeError(
                "打包版里找不到 velch-cli.exe（它与 Velch.exe 应同目录）：无法证明日志管道可用")
        # The packaged console exe dispatches ``--selftest-stream`` itself (see
        # ``packaging/entry_console.py``), so no interpreter flags and no inline source are involved.
        return [executable, "--selftest-stream"]
    return [sys.executable, "-X", "utf8", "-c", STREAM_PROBE]
