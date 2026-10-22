"""Geometry-only tests for the ⑦ 三维模型 screen.

No Tk, no Matplotlib and no solver run: everything here answers "is the picture the same
model the solver integrates?", which is a numerical question about the case's own profile
files.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from velch.ui import model3d
from velch.vehicle import load_vehicle_case

CASE = Path(__file__).resolve().parent.parent / "validation" / "crh380a_m" / "case_frog_N_strip05.json"


@pytest.fixture(scope="module")
def case():
    return load_vehicle_case(CASE)


def test_scene_covers_the_whole_vehicle_and_the_requested_window(case):
    scene = model3d.build_scene(CASE, s_lo=69.0, length_m=6.0, axles=(1, 2),
                                stations=16, points=24, spin=16, case=case)
    assert scene.rails, "所选里程窗内应当有钢轨型面"
    assert len(scene.wheels) == 8, "四个轮对 × 左右两个车轮"
    assert scene.vertex_count == sum(grid.x_m.size for grid in scene.rails + scene.wheels)
    for grid in scene.rails:
        assert grid.x_m.min() >= 69.0 - 1e-9
        assert grid.x_m.max() <= 75.0 + 1e-9


def test_contact_patch_lands_on_the_rail_top(case):
    """The tread radius is ``-z`` of the wheel profile, so the lowest point is the flange tip.

    A 0.43 m centre height against a 0.458 m flange radius puts the flange tip ~28 mm below
    the rail top and the tread on it.  Getting this wrong is invisible in the numbers and
    obvious in the picture, which is why it is pinned here.
    """
    grids = model3d.wheel_grids(case, model3d.initial_states(case), spin=24, points=40)
    lowest = np.array([float(grid.z_m.min()) for grid in grids])
    highest = np.array([float(grid.z_m.max()) for grid in grids])
    centre = np.array([0.5 * (grid.z_m.min() + grid.z_m.max()) for grid in grids])
    assert lowest.min() == pytest.approx(-0.0285, abs=0.004), "轮缘最低点应在轨面下约 28 mm"
    assert highest.max() == pytest.approx(0.888, abs=0.01), "轮缘最高点约 2 x 0.43 + 0.028"
    # 圆盘必须以轮心为心：若 z 少扫一个角度，车轮会被压成一块平板，这条会先坏
    for value, state in zip(centre, model3d.initial_states(case)):
        assert value == pytest.approx(state.z_m, abs=2e-3)


def test_wheel_disc_is_round_not_flat(case):
    """The revolution must sweep x–z, not a single plane: a disc spans the axle height."""
    state = model3d.initial_states(case)[0]
    grids = model3d.wheel_grids(case, (state,), spin=36, points=30)
    grid = grids[0]
    assert grid.shape == (36, min(30, case.wheels[0].profile.y_m.size))
    assert grid.z_m.max() - grid.z_m.min() == pytest.approx(2.0 * 0.458, abs=0.01)
    assert grid.x_m.max() - grid.x_m.min() == pytest.approx(2.0 * 0.458, abs=0.01)


def test_wheelset_uses_the_absolute_centre_height(case):
    state = model3d.initial_states(case)[0]
    assert state.z_m == pytest.approx(case.vehicle.wheel_center_height_m - 0.0005, abs=1e-6)
    assert 0.40 < state.z_m < 0.46


def test_history_states_fall_back_to_the_centre_height(case):
    data = {
        "time_s": np.array([0.0, 0.5]),
        "axle1_y_m": np.array([0.0, 0.001]),
        "axle1_z_m": np.array([-0.0005, -0.0009]),
        "axle1_roll_rad": np.array([0.0, 1e-4]),
    }
    states = model3d.states_from_history(case, list(data), 1, data)
    assert states[0].z_m == pytest.approx(case.vehicle.wheel_center_height_m - 0.0009, abs=1e-9)
    # 第 2–4 轴在 history 里没有通道时，也必须落在轮心高度上而不是 0
    for state in states[1:]:
        assert state.z_m == pytest.approx(case.vehicle.wheel_center_height_m, abs=1e-9)


def test_grid_resolution_is_capped(case):
    scene = model3d.build_scene(CASE, s_lo=69.0, length_m=6.0, axles=(1,),
                                stations=12, points=20, spin=10, case=case)
    for grid in scene.rails:
        assert grid.shape[1] <= 20
        assert grid.x_m.shape[0] <= 14
    for grid in scene.wheels:
        assert grid.shape == (10, min(20, 40 + 1)) or grid.shape[1] <= 41


def test_window_outside_the_profiles_explains_itself(case):
    scene = model3d.build_scene(CASE, s_lo=1.0e5, length_m=5.0, axles=(1,), case=case)
    assert scene.rails == ()
    assert any("没有钢轨型面覆盖" in note for note in scene.notes)


def test_skeleton_puts_the_body_above_the_wheels(case):
    states = model3d.initial_states(case)
    skeleton = model3d.skeleton(case, states)
    assert skeleton["z_wheel_m"] == pytest.approx(float(np.mean([s.z_m for s in states])))
    assert skeleton["z_bogie_m"] > skeleton["z_wheel_m"]
    x0, x1, y0, y1, z0, z1 = skeleton["carbody"]
    assert z1 > z0 > skeleton["z_bogie_m"]
    assert x1 - x0 == pytest.approx(model3d.CARBODY_LENGTH_M)
    assert skeleton["axle_x_m"] == [state.x_m for state in states]


def test_axle_positions_follow_the_travel_speed(case):
    base = model3d.axle_x_positions(case, 0.0)
    later = model3d.axle_x_positions(case, 1.0)
    travel = case.vehicle.travel_speed_m_s
    assert later[0] - base[0] == pytest.approx(travel, rel=1e-9)
    assert later[0] - later[1] == pytest.approx(base[0] - base[1], rel=1e-9)
