"""Console entry point of the packaged product (``velch-cli.exe``).

It is the same command surface as ``python -m velch`` plus the three internal commands a frozen
app needs and a Python interpreter happens to provide for free:

* ``agent-worker <dir>`` -- what ``python -m velch.agent.worker`` does from source;
* ``--selftest-stream`` -- the three-line probe the UI self-test pipes through;
* ``--selftest`` / ``--selftest-json`` -- the UI self-test, run from the console build so CI (and
  the packaging smoke test) can read its output.

That last one exists because the *windowed* exe has no stdout: PyInstaller sets ``sys.stdout`` to
None there, so ``Velch.exe --selftest`` prints nothing when its output is a pipe. Measured in the
first packaged smoke test -- exit code 0, zero bytes captured, self-test reported as "did not run".

Why this file exists at all: in a frozen build ``sys.executable`` is the exe, so
``<exe> -X utf8 -m velch ...`` is not a valid bootstrap.  ``velch.launcher`` therefore starts
children as ``<exe> <command> ...`` and this module is what gives ``<command>`` a meaning.
"""
from __future__ import annotations

import sys


def _utf8_console() -> None:
    """Print UTF-8 no matter what code page the surrounding console is on.

    A frozen console build inherits the console's ANSI code page (cp936 here), so every line of the
    self-test came out as GBK bytes -- readable in a Chinese console, unreadable to any pipe, log
    file, or CI step that assumes UTF-8 (measured: 1629 bytes, all of them mojibake to a UTF-8
    reader).  Everything this product prints is Chinese, so the stream is pinned to UTF-8 here.
    """

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    arguments = list(sys.argv[1:] if argv is None else argv)

    if arguments[:1] == ["--selftest-stream"]:
        for line in ("velch-ui-stream-ok", "velch-ui-stream-ok-2", "argv0=" + sys.argv[0]):
            print(line, flush=True)
        return 0

    if arguments[:1] in (["--selftest"], ["--selftest-json"]):
        # ``run`` is the entry point the UI menu calls; it owns argument parsing for screens and
        # the JSON switch.  (Importing ``main`` here failed the first time -- that name does not
        # exist -- and the packaged exe only reported "Failed to execute script".)
        from velch.ui.selftest import run as selftest_run
        return int(selftest_run(as_json=arguments[0].endswith("json")))

    if arguments[:1] == ["agent-worker"]:
        from velch.agent.worker import main as worker_main
        return int(worker_main(arguments[1:]))

    from velch.cli import main as cli_main
    return int(cli_main(arguments))


if __name__ == "__main__":
    raise SystemExit(main())
