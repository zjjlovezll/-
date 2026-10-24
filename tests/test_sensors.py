"""Tests for measurement-like observables."""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.inverse.sensors import (
    SensorModelError,
    axle_box_acceleration,
    bending_strain_micro,
    differentiate,
    rail_acceleration,
    resample,
    sensor_table,
    wheelset_acceleration,
)
from velch.io.history import Channel, HistoryTable


def _history(channels: dict[str, np.ndarray], rate_hz: float = 2000.0) -> HistoryTable:
    names = sorted(channels)
    arrays = [np.asarray(channels[name], dtype=float) for name in names]
    samples = arrays[0].size
    if any(array.size != samples for array in arrays):
        raise ValueError("test channels must share one length")
    time = np.arange(samples, dtype=float) / rate_hz
    # HistoryTable stores channels as rows: (n_channel, n_time)
    data = np.column_stack(arrays).T
    return HistoryTable(
        schema_version="velch-history-v1",
        time_s=time,
        channels={name: Channel(name=name, unit="-", kind="state") for name in names},
        data=data,
        source="test",
        ordering=tuple(names),
    )


def test_differentiate_twice_recovers_sine_acceleration() -> None:
    rate = 2000.0
    time = np.arange(2000, dtype=float) / rate
    omega = 2.0 * math.pi * 40.0
    values = 1e-4 * np.sin(omega * time)
    acceleration = differentiate(time, values, order=2)
    interior = slice(50, -50)
    expected = -1e-4 * omega ** 2 * np.sin(omega * time)
    error = np.max(np.abs(acceleration[interior] - expected[interior]))
    assert error < 0.02 * np.max(np.abs(expected))


def test_differentiate_rejects_bad_input() -> None:
    with pytest.raises(SensorModelError):
        differentiate([0.0, 1.0, 2.0], [1.0, 2.0])
    with pytest.raises(SensorModelError):
        differentiate([0.0, 0.0, 1.0], [1.0, 2.0, 3.0])
    with pytest.raises(SensorModelError):
        differentiate([0.0, 1.0], [1.0, 2.0], order=2)


def test_wheelset_acceleration_uses_wheelset_channel() -> None:
    rate = 2000.0
    time = np.arange(800, dtype=float) / rate
    omega = 2.0 * math.pi * 25.0
    z = 2e-4 * np.sin(omega * time)
    history = _history({"axle1_z_m": z, "axle2_z_m": z})
    trace = wheelset_acceleration(history, 1)
    assert trace.unit == "m/s^2"
    assert trace.rate_hz == pytest.approx(rate, rel=1e-9)
    assert "lower bound" in trace.note
    interior = slice(50, -50)
    expected = -2e-4 * omega ** 2 * np.sin(omega * time)
    assert np.max(np.abs(trace.values[interior] - expected[interior])) < 0.02 * np.max(np.abs(expected))


def test_rail_acceleration_needs_a_side() -> None:
    history = _history({"axle1_z_m": np.zeros(400), "axle1_right_z_m": np.zeros(400)})
    with pytest.raises(SensorModelError):
        rail_acceleration(history, 1, "middle")
    trace = rail_acceleration(history, 1, "right")
    assert "lumped" in trace.note


def test_missing_channel_is_reported() -> None:
    history = _history({"axle1_z_m": np.zeros(400)})
    with pytest.raises(SensorModelError):
        rail_acceleration(history, 1, "right")


def test_bending_strain_matches_theorem() -> None:
    # M c / (E I): 1e6 N m, c = 0.1 m, E = 210 GPa, I = 1e-5 m^4
    strain = bending_strain_micro(1e6, 210e9, 1e-5, 0.1)
    assert strain == pytest.approx(1e6 * 1e6 * 0.1 / (210e9 * 1e-5), rel=1e-12)
    with pytest.raises(SensorModelError):
        bending_strain_micro(1e6, 0.0, 1e-5, 0.1)


def test_resample_hits_the_requested_rate() -> None:
    time = np.linspace(0.0, 0.1, 1001)
    values = np.sin(2.0 * math.pi * 10.0 * time)
    grid, resampled = resample(time, values, 5120.0)
    assert 1.0 / np.median(np.diff(grid)) == pytest.approx(5120.0, rel=1e-9)
    assert resampled.size == grid.size
    assert np.max(np.abs(resampled - np.sin(2.0 * math.pi * 10.0 * grid))) < 1e-3
    with pytest.raises(SensorModelError):
        resample(time, values, 0.0)


def test_sensor_table_covers_every_axle_and_side() -> None:
    channels: dict[str, np.ndarray] = {}
    for axle in (1, 2, 3, 4):
        channels[f"axle{axle}_z_m"] = np.zeros(400)
        for side in ("left", "right"):
            channels[f"axle{axle}_{side}_z_m"] = np.zeros(400)
    traces = sensor_table(_history(channels))
    names = {trace.name for trace in traces}
    # per axle: one wheelset trace, plus (acceleration, displacement) for each of two sides
    assert len(traces) == 4 * (1 + 2 * 2)
    assert len(names) == len(traces)
    assert "axle1_wheelset_acceleration_z" in names
    assert "axle4_right_rail_displacement_z" in names


# --- axle-box accelerations -------------------------------------------------------------
#
# The solver writes these channels analytically, so the sensor layer must *read* them.  A test that
# only checked the shape would pass on a second difference of the position, which is the mistake
# this function exists to avoid -- so the first test below asserts equality with the channel.

def test_axle_box_acceleration_is_read_not_differentiated() -> None:
    rng = np.random.default_rng(20261024)
    raw = rng.normal(scale=0.3, size=600)          # deliberately not smooth
    history = _history({"axle1_box_left_z_acc_m_per_s2": raw})
    trace = axle_box_acceleration(history, 1, "left")
    assert trace.name == "axle1_box_left_acceleration_z"
    assert trace.unit == "m/s^2"
    assert np.array_equal(trace.values, raw)
    assert "not a differentiated position" in trace.note


def test_axle_box_lateral_is_a_separate_sensor() -> None:
    z = np.linspace(0.0, 1.0, 500)
    y = np.linspace(1.0, 0.0, 500)
    history = _history({
        "axle2_box_right_z_acc_m_per_s2": z,
        "axle2_box_right_y_acc_m_per_s2": y,
    })
    vertical = axle_box_acceleration(history, 2, "right")
    lateral = axle_box_acceleration(history, 2, "right", axis="y")
    assert lateral.name == "axle2_box_right_acceleration_y"
    assert np.array_equal(vertical.values, z)
    assert np.array_equal(lateral.values, y)
    assert not np.array_equal(vertical.values, lateral.values)


def test_axle_box_refuses_an_angular_axis_and_a_bad_side() -> None:
    history = _history({"axle1_box_left_z_acc_m_per_s2": np.zeros(200)})
    with pytest.raises(SensorModelError) as angular:
        axle_box_acceleration(history, 1, "left", axis="pitch")
    assert "rad/s^2" in str(angular.value)
    with pytest.raises(SensorModelError):
        axle_box_acceleration(history, 1, "middle")


def test_axle_box_missing_channel_names_the_column_and_the_fallback() -> None:
    history = _history({"axle1_z_m": np.zeros(200)})
    with pytest.raises(SensorModelError) as excinfo:
        axle_box_acceleration(history, 1, "left")
    message = str(excinfo.value)
    assert "axle1_box_left_z_acc_m_per_s2" in message
    assert "wheelset_acceleration" in message


def test_sensor_table_prefers_the_box_over_the_wheelset_on_the_same_axle() -> None:
    channels: dict[str, np.ndarray] = {"axle1_z_m": np.zeros(300), "axle2_z_m": np.zeros(300)}
    for axis in ("x", "y", "z"):
        channels[f"axle1_box_left_{axis}_acc_m_per_s2"] = np.zeros(300)
    names = {trace.name for trace in sensor_table(_history(channels))}
    # axle 1 has a box: three axes, and no wheelset trace standing in for it
    assert {f"axle1_box_left_acceleration_{axis}" for axis in ("x", "y", "z")} <= names
    assert "axle1_wheelset_acceleration_z" not in names
    # axle 2 has no box: the wheelset channel is the honest fallback
    assert "axle2_wheelset_acceleration_z" in names
