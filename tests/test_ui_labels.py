"""The screens must name things in Chinese; these tests pin the translation.

Two kinds of assertion live here:

* **grammar** — a fixed table of representative columns, so a refactor of the label builder cannot
  silently rename a channel that a person has already learned;
* **coverage** — every column of two real history files, which is what caught ``rail``/``sleeper``
  and ``track_mode`` channels being left untranslated while the fixed table still looked fine.

An unknown column is *allowed* to fall back to its raw name: a wrong Chinese word reads like a
definition and is worse than an identifier.  That fallback is therefore asserted, not forbidden.
"""
from __future__ import annotations

import re

import pytest

from velch.data_root import case_dir
from velch.ui import store

pytestmark = pytest.mark.corpus


CJK = re.compile(r"[\u4e00-\u9fff]")

#: ``(column, expected label)`` — the documented channel grammar, spoken.
GRAMMAR = (
    ("time_s", "时间 [s]"),
    ("axle2_right_normal_n", "第2轴右轨 法向力 [N]"),
    ("axle1_left_active", "第1轴左轨 接触状态 [—]"),
    ("axle4_right_penetration_m", "第4轴右轨 侵入深度 [m]"),
    ("axle1_left_fx_n", "第1轴左轨 纵向蠕滑力 [N]"),
    ("axle1_left_fy_n", "第1轴左轨 横向蠕滑力 [N]"),
    ("axle1_left_fz_n", "第1轴左轨 垂向轮轨力 [N]"),
    ("axle1_y_m", "第1轴 横移 [m]"),
    ("axle1_z_m_per_s", "第1轴 沉浮速度 [m/s]"),
    ("axle1_roll_rad", "第1轴 侧滚角 [rad]"),
    ("axle1_yaw_rad_per_s", "第1轴 摇头角速度 [rad/s]"),
    ("bogie1_z_m", "前转向架 沉浮 [m]"),
    ("carbody_pitch_rad", "车体 点头角 [rad]"),
    ("track_mode12_m", "钢轨 模态位移 12 [m]"),
    ("track_mode3_m_per_s", "钢轨 模态位移 3 [m/s]"),
    ("rail2_z_m", "钢轨2 沉浮 [m]"),
    ("sleeper3_y_m", "轨枕3 横移 [m]"),
    ("axle1_left_rail_z_m", "第1轴左轨 钢轨垂向位移 [m]"),
    ("axle1_left_sleeper_y_m_per_s", "第1轴左轨 轨枕横向位移速度 [m/s]"),
)


@pytest.mark.parametrize(("column", "expected"), GRAMMAR)
def test_channel_label_speaks_the_documented_grammar(column: str, expected: str) -> None:
    assert store.channel_label(column) == expected


def test_unknown_channel_falls_back_to_its_identifier() -> None:
    """No guess: a column outside the grammar keeps its raw name so it stays greppable."""

    column = "some_future_channel_n"
    assert store.channel_label(column) == f"{column} [—]"
    assert store.channel_short_label(column) == column


def test_velocity_columns_are_labelled_as_speeds() -> None:
    assert store.channel_unit("axle2_y_m_per_s") == "m/s"
    assert store.channel_unit("carbody_roll_rad_per_s") == "rad/s"
    assert store.channel_label("carbody_roll_rad_per_s").endswith("速度 [rad/s]")
    # A position suffix must not win over the velocity suffix just because it is shorter-lived.
    assert store.channel_unit("axle2_y_m") == "m"


def test_gate_names_are_all_chinese() -> None:
    for gate, words in store.GATE_LABELS:
        assert CJK.search(words), gate
        assert not re.search(r"[A-Za-z]", words), gate


def test_run_label_keeps_the_directory_name_and_explains_it() -> None:
    run = store.RunInfo(path=case_dir() / "out_full12_cap05",
                        samples=2401, columns=155, method="BDF",
                        gates={"solver_completed": True, "finite_states_and_forces": True})
    label = store.run_label(run)
    assert label.startswith("out_full12_cap05")
    assert "2401 帧" in label
    assert "155 通道" in label
    assert "隐式 BDF" in label
    assert "门 2/2" in label


def test_run_label_without_metadata_still_says_something() -> None:
    """A run directory with no readable manifest must not degrade to a bare identifier."""

    run = store.RunInfo(path=case_dir() / "out_full12_cap05", problem="manifest 缺失")
    assert store.run_label(run) == "out_full12_cap05 · （manifest 缺失）"

    empty = store.RunInfo(path=case_dir() / "out_does_not_exist")
    assert CJK.search(store.run_label(empty))


@pytest.mark.parametrize("run_name", ["out_full12_cap05", "out_AA_full2l"])
def test_every_real_history_column_is_translated(run_name: str) -> None:
    """The coverage test: a new channel family must get words, not slip through as an id."""

    header = case_dir() / run_name / "history.csv"
    if not header.is_file():
        pytest.skip(f"{header} 不存在（语料未挂载）")
    columns = store.history_columns(header)
    missing = [column for column in columns if not CJK.search(store.channel_label(column))]
    assert not missing, f"{run_name} 仍有未翻译通道: {missing[:8]}"
