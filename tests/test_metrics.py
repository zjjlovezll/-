"""Tests for the standard assessment indices."""

from __future__ import annotations

from pathlib import Path

import pytest

from velch.metrics import (AssessmentError, AssessmentLimits, assess_history,
                           format_assessment, mean_axle_load_n)


def write_history(path: Path, rows: list[tuple[float, float, float, float]]) -> Path:
    """rows = (P_left, P_right, fy_left, fy_right) for axle 1 (both sides active)."""

    header = ["time_s", "axle1_left_normal_n", "axle1_right_normal_n",
              "axle1_left_fy_n", "axle1_right_fy_n",
              "axle1_left_active", "axle1_right_active"]
    lines = [",".join(header)]
    for index, (p_l, p_r, q_l, q_r) in enumerate(rows):
        lines.append(f"{index*0.001},{p_l},{p_r},{q_l},{q_r},1,1")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_indices_from_a_known_row(tmp_path: Path) -> None:
    history = write_history(tmp_path / "history.csv", [
        (60_000.0, 60_000.0, 0.0, 0.0),
        (40_000.0, 80_000.0, 36_000.0, 8_000.0),
    ])
    assessment = assess_history(history)
    axle = assessment.axles[0]
    assert axle.samples == 2
    assert axle.derailment_coefficient == pytest.approx(36_000.0 / 40_000.0)
    assert axle.derailment_side == "left"
    # P̄ = 60 kN, min = 40 kN  ->  dP/P = 1/3
    assert axle.wheel_load_reduction == pytest.approx(1.0 / 3.0)
    # H = |36 + 8| kN
    assert axle.lateral_force_n == pytest.approx(44_000.0)
    # Mean axle load = (P_L + P_R) / 2 averaged over samples = 120 kN.
    assert assessment.static_axle_load_n == pytest.approx(120_000.0)


def test_run_directory_is_accepted(tmp_path: Path) -> None:
    directory = tmp_path / "run"
    directory.mkdir()
    write_history(directory / "history.csv", [(60_000.0, 60_000.0, 0.0, 0.0)])
    assert assess_history(directory).samples == 1
    assert mean_axle_load_n(directory) == pytest.approx(120_000.0)


def test_verdict_uses_the_static_axle_load_for_the_lateral_limit(tmp_path: Path) -> None:
    history = write_history(tmp_path / "history.csv", [
        (75_000.0, 75_000.0, 20_000.0, -5_000.0),
    ])
    assessment = assess_history(history, static_axle_load_n=150_000.0)
    verdict = assessment.verdict(150_000.0)
    # H limit = 10 + 150/3 = 60 kN; H = 15 kN -> pass; no derailment either.
    assert verdict["checks"]["axle_lateral_force_n"]["limit"] == pytest.approx(60_000.0)
    assert verdict["pass"] is True

    strict = AssessmentLimits(derailment_coefficient_max=0.1)
    failing = assess_history(history, static_axle_load_n=150_000.0, limits=strict)
    assert failing.verdict(150_000.0)["pass"] is False
    assert "overall: FAIL" in format_assessment(failing, 150_000.0)


def test_missing_force_columns_fail_loudly(tmp_path: Path) -> None:
    path = tmp_path / "history.csv"
    path.write_text("time_s,axle1_x_m\n0,1\n", encoding="utf-8")
    with pytest.raises(AssessmentError):
        assess_history(path)
    with pytest.raises(AssessmentError):
        assess_history(tmp_path / "absent")
