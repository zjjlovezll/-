"""The operator's gain must not depend on how much patch it was measured over."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RESULT = Path(r"F:\velch_tmp\operator_design\verdict.json")


def _load() -> dict:
    if not RESULT.exists():
        pytest.skip("run scripts/s19_operator_design.py first")
    return json.loads(RESULT.read_text(encoding="utf-8"))


def _table(payload: dict) -> dict[str, dict[float, float]]:
    table: dict[str, dict[float, float]] = {}
    for row in payload["rows"]:
        table.setdefault(row["design_id"], {})[float(row["speed_kmh"])] = float(row["gain_per_m"])
    return table


def test_two_designs_agree_within_one_percent() -> None:
    table = _table(_load())
    common = sorted(set(table["A_240"]) & set(table["B_790"]))
    assert len(common) >= 4, common
    for speed in common:
        ratio = table["A_240"][speed] / table["B_790"][speed]
        # 240 vs 790 periods is a 3.3x length difference; the readings must not care.
        assert ratio == pytest.approx(1.0, abs=0.01), (speed, ratio)


def test_the_gain_falls_with_speed() -> None:
    table = _table(_load())
    for design, rows in table.items():
        speeds = sorted(rows)
        gains = [rows[speed] for speed in speeds]
        assert all(earlier > later for earlier, later in zip(gains, gains[1:])), (design, gains)


def test_the_speed_effect_is_worth_a_table() -> None:
    table = _table(_load())
    rows = table["A_240"]
    speeds = sorted(rows)
    spread = rows[speeds[0]] / rows[speeds[-1]] - 1.0
    # Below 10 % it would not justify a per-speed table at all; above 50 % the model would be wrong.
    assert 0.10 < spread < 0.50, spread


def test_the_calibration_speed_reproduces_the_published_operator() -> None:
    table = _table(_load())
    speed = min(table["A_240"], key=lambda value: abs(value - 70.8))
    assert abs(speed - 70.8) < 0.05, speed
    # s16 published 2.755e4 from one design over the whole record; the windowed value must match it,
    # which is what proves the window -- not the design -- was the difference measured in round 62.
    assert table["A_240"][speed] == pytest.approx(2.755e4, rel=0.01)
