"""`velch --version` 必须答出版本（正式发布的命令行不该只会报"缺少子命令"）。"""
from __future__ import annotations

import contextlib
import io

import pytest

from velch import __version__, cli


def test_version_flag_prints_the_package_version() -> None:
    buffer = io.StringIO()
    with pytest.raises(SystemExit) as exit_info, contextlib.redirect_stdout(buffer):
        cli.main(["--version"])

    assert exit_info.value.code == 0
    assert __version__ in buffer.getvalue()
    assert buffer.getvalue().startswith("velch ")


def test_no_arguments_still_complains_about_the_missing_command() -> None:
    buffer = io.StringIO()
    with pytest.raises(SystemExit) as exit_info, contextlib.redirect_stderr(buffer):
        cli.main([])

    assert exit_info.value.code == 2
    assert "required: command" in buffer.getvalue()
