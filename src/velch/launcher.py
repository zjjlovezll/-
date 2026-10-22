"""One place that knows how to start Velch's own subprocesses.

Every screen that runs a case used to hardcode ``[sys.executable, "-X", "utf8", "-m", "velch", ...]``.
That works from a source checkout and fails the moment the product is a real executable: in a
frozen build ``sys.executable`` *is* ``Velch.exe``, and ``-X utf8 -m velch`` is not a valid way to
start it.  The failure was invisible until packaging, which is exactly why it survived.

Rules:

* running from source → ``<python> -X utf8 -m velch <command> ...`` (UTF-8 forced, entry module)
* frozen → ``<same exe> <command> ...`` because the exe *is* the entry point; UTF-8 comes from the
  launcher (``PYTHONUTF8=1``) since ``-X`` has no meaning to a frozen bootstrap
* a background worker keeps its own module entry (``velch.agent.worker``) from source; frozen it
  becomes ``<exe> agent-worker <dir>`` so the packaged app can still run detached jobs.
"""
from __future__ import annotations

import sys
from pathlib import Path

#: Commands that the frozen executable must dispatch itself.  The console entry point (``velch``)
#: routes them; the windowed one refuses them with a message rather than a stack trace.
FROZEN_COMMANDS: tuple[str, ...] = ("run", "run-vehicle", "run-vehicle-batch", "assess",
                                    "speedsweep", "agent", "agent-worker")


def is_frozen() -> bool:
    """True inside a PyInstaller (or similar) bundle."""

    return bool(getattr(sys, "frozen", False))


def console_executable() -> str:
    """The console sibling of the windowed exe, when the build ships one.

    A windowed build has no stdout: its children must not inherit it or every log line vanishes.
    The package therefore ships ``Velch.exe`` (windowed) next to ``velch-cli.exe`` (console), and
    the children are started with the console one.  From source this is just the interpreter.

    (The console exe is *not* ``velch.exe``: Windows file names are case-insensitive, so it would
    collide with ``Velch.exe`` inside one PyInstaller COLLECT and one of the two would vanish.)
    """

    if not is_frozen():
        return sys.executable
    current = Path(sys.executable)
    if "cli" in current.stem.lower():
        # Already the console build (the self-test can be started through it): it has a stdout, so
        # it is its own correct answer.  Looking for a *sibling* named velch-cli.exe while running
        # as velch-cli.exe made the log-pipe probe believe the sibling was missing and refuse to
        # run -- a false alarm that cost one packaged smoke round.
        return str(current)
    candidate = current.with_name("velch-cli.exe")
    return str(candidate) if candidate.is_file() else str(current)


def launcher_argv(*args: str) -> list[str]:
    """Argv for a Velch child process, valid from source and from a frozen build."""

    parts = [str(part) for part in args]
    if not parts:
        raise ValueError("launcher_argv needs a command")
    if is_frozen():
        command = parts[0]
        if command == "velch":
            # ``launcher_argv("velch", "run-vehicle", ...)`` reads naturally at the call site but
            # the exe already *is* velch; drop the redundant module name.
            parts = parts[1:]
        if not parts:
            raise ValueError("launcher_argv: command missing after 'velch'")
        return [console_executable(), *parts]
    return [sys.executable, "-X", "utf8", "-m", "velch", *parts]


def worker_argv(job_dir: object) -> list[str]:
    """Argv for the detached job worker (``python -m velch.agent.worker <dir>`` from source)."""

    if is_frozen():
        return [console_executable(), "agent-worker", str(job_dir)]
    return [sys.executable, "-X", "utf8", "-m", "velch.agent.worker", str(job_dir)]


def child_environment(env: dict[str, str]) -> dict[str, str]:
    """Force UTF-8 for a child process; ``-X utf8`` is unavailable to a frozen bootstrap."""

    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env
