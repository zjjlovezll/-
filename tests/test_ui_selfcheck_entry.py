"""An entry test: the ① screen must offer a way to run the environment check."""
from __future__ import annotations

from pathlib import Path

TEXT = (Path(__file__).resolve().parent.parent / "src" / "velch" / "ui" / "screen_cases.py").read_text(
    encoding="utf-8")
DIALOG = (Path(__file__).resolve().parent.parent / "src" / "velch" / "ui" / "selfcheck_dialog.py"
          ).read_text(encoding="utf-8")


def test_the_cases_screen_offers_a_selfcheck_button() -> None:
    assert '"环境体检"' in TEXT
    assert "self.run_selfcheck" in TEXT


def test_the_dialog_runs_the_cli_instead_of_importing_the_checker() -> None:
    # 冻结包里 Velch.exe 没 stdout；自检必须走 velch-cli.exe，也就是 launcher_argv。
    assert 'launcher_argv("selfcheck")' in DIALOG
    assert "from velch.selfcheck import" not in DIALOG
    # 从 ``..launcher`` 取叶子，而不是 ``from .. import launcher``：后者在架构规则里会被记成
    # ``velch``（包本身），而 presentation 不许 import 包根。
    assert "from ..launcher import launcher_argv" in DIALOG


def test_the_dialog_colours_the_three_verdicts() -> None:
    for marker in ('"[FAIL]"', '"[WARN]"', '"[PASS]"'):
        assert marker in DIALOG
    assert 'tag_configure("fail"' in DIALOG


def test_the_dialog_localises_every_write_behind_one_append() -> None:
    """结果区是给人读的证据，不是输入框：只允许 ``_append`` 改它，并且每次改完必须复原只读。"""

    assert DIALOG.count('state="normal"') == 1, "只有 _append 允许解锁文本区"
    body = DIALOG.split("def _append(")[1].split("def ")[0]
    assert body.index('state="normal"') < body.index('state="disabled"'), "写入后必须回到只读"
    assert body.rstrip().endswith('configure(state="disabled")') or 'disabled' in body.rstrip()[-80:]
