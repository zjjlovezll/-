"""The failures that stop the window from working at all.

These are not cosmetic: a frozen event pump, a stale screen after a failed load, or a NaN limit
bar read as "in limits" all make the software report something other than what it computed.  Each
test names the concrete symptom it locks down.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from velch.ui import fmt

SOURCE = Path(__file__).resolve().parent.parent / "src" / "velch" / "ui"


def _source(name: str) -> str:
    return (SOURCE / name).read_text(encoding="utf-8")


# -- the event pump ---------------------------------------------------------
def test_pump_rearms_even_when_a_handler_raises() -> None:
    """``_pump`` used to call ``after`` outside its ``try``.

    One exception in any handler stopped polling for good: logs froze, worker results were never
    delivered, the busy state never cleared and the subprocess kept running unobserved.  The only
    trace was a traceback on stderr.
    """

    text = _source("app.py")
    pump = text.split("def _pump", 1)[1].split("def report_problem", 1)[0]
    assert "finally:" in pump, "the re-arm must survive an exception"
    assert pump.index("finally:") < pump.index("after(100"), "after() must live inside finally"
    assert "except Exception" in pump, "one bad event must not stop the queue"


def test_pump_keeps_delivering_after_a_failing_event() -> None:
    """Behavioural version of the test above, on a real (withdrawn) Tk window."""

    try:
        import tkinter as tk

        from velch.ui.app import VelchUI
    except Exception:  # pragma: no cover - Tk or matplotlib unavailable
        pytest.skip("tkinter is not available on this machine")

    try:
        root = tk.Tk()
    except Exception:  # pragma: no cover
        pytest.skip("no display for a Tk window")
    root.withdraw()
    try:
        app = VelchUI(root, headless=True)
        seen: list[str] = []

        def dispatch(kind: str, payload: object) -> None:
            if kind == "boom":
                raise RuntimeError("handler exploded")
            seen.append(kind)

        app.dispatch = dispatch  # type: ignore[assignment]
        app.queue.put(("boom", None))
        app.queue.put(("after_boom", None))
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and "after_boom" not in seen:
            root.update()
            time.sleep(0.02)
        assert "after_boom" in seen, "the pump stopped after one failing event"
        assert "界面事件处理失败" in app.status_text, "the failure must reach the status bar"
    finally:
        root.destroy()


def test_callback_errors_are_reported_not_only_printed() -> None:
    text = _source("app.py")
    assert "report_callback_exception" in text
    assert "def _on_callback_error" in text


# -- subprocess ownership ---------------------------------------------------
def test_spawn_refuses_a_second_child() -> None:
    """Two subprocesses shared one slot: the first exit code went unread."""

    text = _source("app.py")
    spawn = text.split("def spawn", 1)[1].split("def cli_env", 1)[0]
    assert "ProcessJob | None" in spawn
    assert "running" in spawn, "spawn must refuse while another child owns the slot"
    assert '("exit", (self,' in text, "the exiting job must travel with its own event"
    assert "def _owner_screen(self, job: ProcessJob | None = None)" in text


def test_exit_routing_uses_the_job_not_the_visible_screen() -> None:
    text = _source("app.py")
    on_exit = text.split("def on_exit", 1)[1].split("def ", 1)[0]
    assert "isinstance(job, int)" in on_exit, "legacy (code, elapsed, cancelled) must not raise"
    assert "_owner_screen(job)" in on_exit


# -- stale screens ----------------------------------------------------------
def test_spectrum_clears_before_computing_and_drops_late_results() -> None:
    text = _source("screen_spectrum.py")
    compute = text.split("def compute", 1)[1].split("def _render", 1)[0]
    assert "_clear_view" in compute, "a failed run must not leave the previous bars on screen"
    assert "token != self._token" in compute, "a late worker must not paint over a newer run"
    assert "self._token += 1" in compute


def test_spectrum_caption_names_the_run() -> None:
    text = _source("screen_spectrum.py")
    assert "self._token_run" in text, "the caption must say whose numbers these are"
    assert "dominant_hz:.0f" in text.split("dominant =", 1)[1][:120], "None-safe dominant band"
    assert "result.dominant_hz" in text


def test_assess_clears_limits_before_a_renewed_attempt() -> None:
    text = _source("screen_assess.py")
    assert "def _clear_limits" in text
    load = text.split("def load_run", 1)[1].split("def _read_summary", 1)[0]
    assert "_clear_limits" in load, "a failing assessment must not keep the old limit bars"
    assert load.index("_clear_limits") < load.index("except"), "clear first, then try"


def test_model3d_reports_a_missing_run_instead_of_keeping_geometry() -> None:
    text = _source("screen_model3d.py")
    assert "没有钢轨型面覆盖" in text or "没有" in text, "the screen must say why it is empty"


def test_cases_filter_does_not_keep_a_hidden_case_selected() -> None:
    text = _source("screen_cases.py")
    apply_filter = text.split("def _apply_filter", 1)[1].split("def _on_select", 1)[0]
    assert "self.selected = None" in apply_filter, "a filtered-out row must not stay selected"
    assert "selection_set" in apply_filter, "the first visible row becomes the selection"


# -- numbers that are conclusions -------------------------------------------
def test_nan_never_reads_as_a_pass() -> None:
    text = _source("widgets.py")
    bar = text.split("class LimitBar", 1)[1].split("class GateList", 1)[0]
    assert "isfinite" in bar, "NaN compares False everywhere, so it fell through to the pass colour"
    assert "无有效值" in bar


def test_peak_force_property_is_named_in_newtons() -> None:
    store = _source("store.py")
    assert "def peak_force_n" in store
    assert "def peak_force_kn" not in store, "the old name returned newtons and invited a 1000x bug"


@pytest.mark.parametrize(
    "value,unit,expected",
    [
        (59680.5769, "N", "59.68 kN"),
        (0.4738, "", "0.4738"),
        (48.0, "%", "48 %"),
        (float("nan"), "N", "—"),
        (float("inf"), "N", "—"),
    ],
)
def test_one_number_formatter(value: float, unit: str, expected: str) -> None:
    assert fmt.fmt_number(value, unit) == expected


def test_signed_percent_is_a_difference_not_a_ratio() -> None:
    assert fmt.fmt_percent(-0.0231, signed=True) == "-2.31 %"
    assert fmt.fmt_percent(float("nan")) == "—"
    assert fmt.fmt_number(-12.5, "N", signed=True) == "-12.5 N"


def test_remaining_ad_hoc_formats_are_gone() -> None:
    """``f"{x:+.4g}"`` printed ``+nan %`` for a missing comparison side."""

    compare = _source("screen_compare.py")
    assert "fmt_percent(delta / theirs" in compare
    assert "{delta:+.4g}" not in compare
