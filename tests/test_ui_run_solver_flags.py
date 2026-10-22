"""Pin the solver row on screen ② to the flags the CLI actually accepts.

The row is a translation layer only: it must never rewrite the case file, and it must not invent
flags.  If ``run-vehicle`` renames or drops one, this test fails before a user gets a
"unrecognized arguments" error after clicking 启动.
"""
from __future__ import annotations

import inspect

import pytest

import velch.cli as cli
from velch.ui.screen_run import RunScreen


def test_the_choices_cover_what_the_runner_understands() -> None:
    assert set(value for value in RunScreen.METHOD_VALUES if value) <= {"DOP853", "Radau", "BDF"}
    assert set(value for value in RunScreen.JACOBIAN_VALUES if value) <= {
        "analytic", "sparse_fd", "none"
    }
    # Index-aligned: the label at i must map to the value at i.
    assert len(RunScreen.METHOD_CHOICES) == len(RunScreen.METHOD_VALUES)
    assert len(RunScreen.JACOBIAN_CHOICES) == len(RunScreen.JACOBIAN_VALUES)


def test_the_runner_still_accepts_every_flag_the_screen_passes() -> None:
    source = inspect.getsource(cli)
    for flag in ("--fast", "--method", "--jacobian", "--rtol"):
        assert flag in source, f"velch.cli lost {flag}"


def test_the_default_row_adds_no_flags() -> None:
    """'按算例声明' must mean silence, not a hidden default overriding the case file."""

    screen = RunScreen.__new__(RunScreen)
    screen.fast_var = _FakeVar(False)
    screen.method_var = _FakeVar(RunScreen.METHOD_CHOICES[0])
    screen.jacobian_var = _FakeVar(RunScreen.JACOBIAN_CHOICES[0])
    screen.rtol_var = _FakeVar("")
    assert RunScreen._solver_flags(screen) == []


def test_the_fast_preset_is_one_flag() -> None:
    screen = RunScreen.__new__(RunScreen)
    screen.fast_var = _FakeVar(True)
    screen.method_var = _FakeVar(RunScreen.METHOD_CHOICES[0])
    screen.jacobian_var = _FakeVar(RunScreen.JACOBIAN_CHOICES[0])
    screen.rtol_var = _FakeVar("")
    assert RunScreen._solver_flags(screen) == ["--fast"]


def test_overrides_survive_next_to_the_preset() -> None:
    """--fast sets a baseline; an explicit pick still wins, which is the CLI's documented order."""

    screen = RunScreen.__new__(RunScreen)
    screen.fast_var = _FakeVar(True)
    screen.method_var = _FakeVar("隐式 BDF")
    screen.jacobian_var = _FakeVar("解析（隐式专用）")
    screen.rtol_var = _FakeVar("1e-5")
    assert RunScreen._solver_flags(screen) == [
        "--fast", "--method", "BDF", "--jacobian", "analytic", "--rtol", "1e-5"
    ]


class _FakeVar:
    """Enough of a ``tk.StringVar``/``BooleanVar`` for the pure flag translation."""

    def __init__(self, value) -> None:
        self._value = value

    def get(self):
        return self._value


def test_the_screen_never_touches_the_case_file() -> None:
    source = inspect.getsource(RunScreen)
    assert "write_text" not in source
    assert "json.dump" not in source
    assert "replace(" not in source


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
