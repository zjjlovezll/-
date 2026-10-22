"""The startup helper must give the same product from source and from a frozen build.

Two things are being pinned here:

* with no ``sys.frozen`` the child runs ``<python> -X utf8 -m velch <command>`` (UTF-8 forced);
* with ``sys.frozen`` the exe *is* the entry point, so ``-X utf8 -m velch`` must not appear --
  that exact string silently broke "run a case from the window" in a packaged build, and nothing
  in the test suite could see it because a source checkout never takes that branch.
"""
from __future__ import annotations

import sys

import pytest

from velch import launcher


@pytest.fixture()
def frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    return sys


def test_source_argv_forces_utf8_and_uses_the_module_entry():
    argv = launcher.launcher_argv("run-vehicle", "case.json")
    assert argv[:5] == [sys.executable, "-X", "utf8", "-m", "velch"]
    assert argv[5:] == ["run-vehicle", "case.json"]


def test_frozen_argv_is_the_exe_itself(frozen):
    argv = launcher.launcher_argv("run-vehicle", "case.json")
    assert argv == [sys.executable, "run-vehicle", "case.json"]
    assert "-X" not in argv and "-m" not in argv


def test_frozen_argv_drops_a_redundant_velch_prefix(frozen):
    assert launcher.launcher_argv("velch", "assess", "run") == [sys.executable, "assess", "run"]


def test_worker_argv_switches_entry_between_modes(monkeypatch):
    from_source = launcher.worker_argv("jobdir")
    assert from_source[:4] == [sys.executable, "-X", "utf8", "-m"]
    assert from_source[4] == "velch.agent.worker"
    # frozen: the exe dispatches the command itself
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert launcher.worker_argv("jobdir") == [sys.executable, "agent-worker", "jobdir"]


def test_child_environment_forces_utf8_without_overwriting_the_caller():
    env = launcher.child_environment({"PATH": "x"})
    assert env["PYTHONUTF8"] == "1" and env["PYTHONIOENCODING"] == "utf-8"
    assert launcher.child_environment({"PYTHONUTF8": "0"})["PYTHONUTF8"] == "0"


def test_launcher_needs_a_command():
    with pytest.raises(ValueError):
        launcher.launcher_argv()


def test_no_module_reaches_for_sys_executable_directly():
    """A stray ``[sys.executable, "-X", "utf8", "-m", "velch", ...]`` would regress silently."""

    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "src" / "velch"
    # ``launcher.py`` builds argv; ``ui/stream_probe.py`` builds the probe argv; ``data_root.py``
    # reads ``sys.executable`` only to locate the install folder (never to start anything).
    builders = {"launcher.py", "stream_probe.py", "data_root.py"}
    offenders = []
    for path in sorted(root.rglob("*.py")):
        if path.name in builders:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "sys.executable" in line:
                offenders.append(f"{path.relative_to(root)}:{number}")
    assert offenders == [], "use velch.launcher instead of sys.executable: " + ", ".join(offenders)
