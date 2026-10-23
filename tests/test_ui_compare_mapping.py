"""O003：对照屏必须常驻说明"猜了哪两列"，而且能区分自动与手动。"""
from __future__ import annotations

from pathlib import Path

from velch.ui import screen_compare as module

SOURCE = Path(module.__file__).read_text(encoding="utf-8")


def test_the_guess_is_shown_in_the_panel_not_only_the_status_bar() -> None:
    # 状态栏那句话下一次操作就没了；面板上的这一行必须存在且被 wrap_with 跟随宽度。
    assert "self.mapping_var" in SOURCE
    assert "self.mapping_label" in SOURCE
    assert "self.wrap_with(self.mapping_label" in SOURCE


def test_choosing_a_column_by_hand_switches_the_wording() -> None:
    assert "手动选择" in SOURCE
    assert "另有 {" in SOURCE or "另有 " in SOURCE


def test_a_second_candidate_is_admitted_rather_than_hidden() -> None:
    # "猜错的代价是整张对照图比较了两根不同的轨" 这句必须留在代码里：它是这条提示存在的理由。
    assert "两根不同的轨" in SOURCE


def test_both_combos_report_back() -> None:
    assert SOURCE.count("self._describe_mapping()") >= 3
    assert 'self.station_combo.bind("<<ComboboxSelected>>"' in SOURCE
    assert 'self.force_combo.bind("<<ComboboxSelected>>"' in SOURCE


def test_an_unrecognisable_header_says_so() -> None:
    assert "列名无法识别" in SOURCE
    assert "fallback" in SOURCE


def test_the_screen_still_does_not_touch_the_solver() -> None:
    for forbidden in ("vehicle_solver", "simulate_vehicle", "jacobian"):
        assert forbidden not in SOURCE
