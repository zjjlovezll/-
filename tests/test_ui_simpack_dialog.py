"""The Simpack import dialog must speak the CLI's language and nothing else."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from velch.ui import simpack_dialog
from velch.ui.simpack_dialog import _parse_report, _status_line

SOURCE = Path(__file__).resolve().parent.parent / "src" / "velch"


_ROOT = None


def _root():
    """The one Tk root this module uses; never skipped silently after a transient failure.

    Creating a second interpreter while another test still holds one can fail once and succeed on
    the next try -- earlier this file turned that into a skip, which is how "seven screens green"
    and "one random test skipped" coexisted. Retry a few times, and only then decide: skip when the
    machine has no display at all (``VELCH_HEADLESS=1`` makes that explicit), fail otherwise.
    """

    global _ROOT
    if _ROOT is not None:
        return _ROOT
    tk = pytest.importorskip("tkinter")
    last: Exception | None = None
    for _attempt in range(3):
        try:
            root = tk.Tk()
        except tk.TclError as error:  # pragma: no cover - headless CI only
            last = error
            time.sleep(0.2)
            continue
        root.withdraw()
        _ROOT = root
        return root
    if os.environ.get("VELCH_HEADLESS"):
        pytest.skip(f"headless: {last}")
    pytest.fail(f"Tk could not open a window after 3 tries: {last} "
                "(set VELCH_HEADLESS=1 if this machine really has no display)")


def _dialog(monkeypatch, tmp_path: Path):
    """Build the dialog headless; skip only when Tk genuinely cannot open a window."""

    root = _root()
    dialog = simpack_dialog.SimpackImportDialog(root, template=tmp_path / "case_A.json",
                                                case_dir=tmp_path)
    return root, dialog


@pytest.fixture(scope="module", autouse=True)
def _close_root():
    yield
    global _ROOT
    if _ROOT is not None:
        _ROOT.destroy()
        _ROOT = None


def test_the_command_is_the_cli_command(monkeypatch, tmp_path: Path) -> None:
    root, dialog = _dialog(monkeypatch, tmp_path)
    try:
        dialog.catalog.set(str(tmp_path / "catalog.json"))
        dialog.case_id.set("simpack_probe")
        command = dialog.build_command()
        assert command[:5] == [sys.executable, "-X", "utf8", "-m", "velch"]
        assert command[5] == "simpack-case"
        assert "--catalog" in command and "--template" in command
        assert command[command.index("--out") + 1] == str(tmp_path / "simpack_probe.json")
        assert "--sample" in command and command[command.index("--sample") + 1] == "60"
        assert "--keep-profiles" not in command
        assert "--no-seat-check" not in command
    finally:
        dialog.destroy()


def test_the_two_switches_are_opt_in(monkeypatch, tmp_path: Path) -> None:
    root, dialog = _dialog(monkeypatch, tmp_path)
    try:
        dialog.catalog.set(str(tmp_path / "catalog.json"))
        dialog.keep_profiles.set(True)
        dialog.seat_check.set(False)
        dialog.rail.set("R")
        command = dialog.build_command()
        assert "--keep-profiles" in command
        assert "--no-seat-check" in command
        assert command[command.index("--rail") + 1] == "R"
    finally:
        dialog.destroy()


def test_a_missing_catalog_is_refused_with_words_not_a_traceback(monkeypatch,
                                                                tmp_path: Path) -> None:
    root, dialog = _dialog(monkeypatch, tmp_path)
    try:
        with pytest.raises(ValueError, match="catalog.json"):
            dialog.build_command()
    finally:
        dialog.destroy()


def test_derive_does_not_swallow_a_failing_command(monkeypatch, tmp_path: Path) -> None:
    root, dialog = _dialog(monkeypatch, tmp_path)
    try:
        dialog.catalog.set(str(tmp_path / "catalog.json"))
        monkeypatch.setattr(dialog, "_run", lambda _command: (2, '{"seating": {"seats": false}}'))
        called: list[Path] = []
        dialog._on_done = called.append
        dialog.derive()
        assert dialog.report == {"seating": {"seats": False}}
        assert called == []                       # a refusal must not reload the list as success
        assert "没坐住" in dialog.status.cget("text")
    finally:
        dialog.destroy()


def test_a_successful_derive_hands_back_the_file(monkeypatch, tmp_path: Path) -> None:
    root, dialog = _dialog(monkeypatch, tmp_path)
    try:
        dialog.catalog.set(str(tmp_path / "catalog.json"))
        dialog.case_id.set("simpack_ok")
        payload = '{\n  "seating": {"seats": true, "residual_n": 1.1e-07}\n}\n'
        monkeypatch.setattr(dialog, "_run", lambda _command: (0, payload))
        called: list[Path] = []
        dialog._on_done = called.append
        dialog.derive()
        assert called == [tmp_path / "simpack_ok.json"]
        assert "坐住了" in dialog.status.cget("text")
    finally:
        dialog.destroy()


def test_the_report_parser_survives_noise() -> None:
    assert _parse_report('warning: something\n{"a": 1}') == {"a": 1}
    assert _parse_report("no json here") is None
    assert _parse_report('{"broken": ') is None


def test_the_status_line_distinguishes_three_outcomes() -> None:
    assert "未跑静平衡" in _status_line(0, {"crown_delta_mm": {}})
    assert "坐住了" in _status_line(0, {"seating": {"seats": True, "residual_n": 1e-7}})
    assert "没坐住" in _status_line(2, {"seating": {"seats": False}})
    assert "退出码 3" in _status_line(3, None)


def test_the_dialog_does_not_import_the_forward_stack() -> None:
    source = (SOURCE / "ui" / "simpack_dialog.py").read_text(encoding="utf-8")
    for forbidden in ("vehicle_solver", "velch.contact", "velch.jacobian", "import numpy"):
        assert forbidden not in source, forbidden
    assert "launcher_argv" in source
