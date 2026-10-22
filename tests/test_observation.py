"""Tests for the typed history schema and the observation/alignment layer."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from velch.inverse import ChannelSpec, ObservationError, ObservationSet, align
from velch.io.history import (
    HISTORY_SCHEMA,
    Channel,
    HistoryError,
    HistoryTable,
    channel_names,
    classify,
    read_history,
    write_history,
)


def _history(time: np.ndarray, columns: dict[str, np.ndarray]) -> HistoryTable:
    names = tuple(columns)
    data = np.array([columns[name] for name in names], dtype=float)
    return HistoryTable(HISTORY_SCHEMA, time,
                        {name: classify(name) for name in names}, data, "synthetic", names)


def test_classify_units_and_kinds() -> None:
    assert classify("time_s") == Channel("time_s", "s", "time")
    assert classify("axle1_z_m") == Channel("axle1_z_m", "m", "state")
    assert classify("axle1_roll_rad") == Channel("axle1_roll_rad", "rad", "state")
    assert classify("axle1_y_m_per_s") == Channel("axle1_y_m_per_s", "m/s", "velocity")
    assert classify("axle1_roll_rad_per_s") == Channel("axle1_roll_rad_per_s", "rad/s", "velocity")
    assert classify("axle1_right_normal_n") == Channel("axle1_right_normal_n", "N", "force")
    assert classify("axle1_right_fx_n") == Channel("axle1_right_fx_n", "N", "force")
    assert classify("axle1_right_penetration_m") == Channel(
        "axle1_right_penetration_m", "m", "contact")
    assert classify("axle1_right_active") == Channel("axle1_right_active", "-", "flag")
    assert classify("carbody_roll_nm") == Channel("carbody_roll_nm", "N*m", "moment")
    with pytest.raises(HistoryError):
        classify("axle1_mystery")


def test_channel_registry_is_classifiable() -> None:
    names = channel_names()
    assert "time_s" in names
    assert "axle4_left_normal_n" in names
    for name in names:
        assert classify(name).name == name


def test_history_round_trip(tmp_path: Path) -> None:
    time = np.linspace(0.0, 0.1, 11)
    table = _history(time, {
        "time_s": time,
        "axle1_z_m": np.full_like(time, -0.4295),
        "axle1_right_normal_n": np.linspace(50e3, 60e3, 11),
    })
    path = write_history(tmp_path / "history.csv", table)
    back = read_history(path)
    assert back.samples == 11
    assert back.ordering == table.ordering
    assert back.channels["axle1_right_normal_n"].unit == "N"
    assert np.allclose(back["axle1_right_normal_n"], table["axle1_right_normal_n"])


def test_history_select_and_errors(tmp_path: Path) -> None:
    time = np.linspace(0.0, 0.1, 5)
    table = _history(time, {"time_s": time, "axle1_z_m": np.zeros(5),
                            "axle1_left_normal_n": np.ones(5)})
    picked = table.select(["time_s", "axle1_left_normal_n"])
    assert picked.ordering == ("time_s", "axle1_left_normal_n")
    assert picked.samples == 5
    with pytest.raises(HistoryError):
        table.select(["nope_m"])
    with pytest.raises(HistoryError):
        table["nope_m"]
    forces = table.where(lambda channel: channel.kind == "force")
    assert forces.ordering == ("axle1_left_normal_n",)
    with pytest.raises(HistoryError):
        read_history(tmp_path / "missing.csv")


def test_observation_from_history_checks_units() -> None:
    time = np.linspace(0.0, 0.1, 5)
    table = _history(time, {"time_s": time, "axle1_right_normal_n": np.full(5, 1e5)})
    good = ObservationSet.from_history(table, [ChannelSpec("axle1_right_normal_n", "N")])
    assert good.names == ("axle1_right_normal_n",)
    with pytest.raises(ObservationError):
        ObservationSet.from_history(table, [ChannelSpec("axle1_right_normal_n", "kN")])
    with pytest.raises(ObservationError):
        ObservationSet.from_history(table, [ChannelSpec("axle1_left_normal_n", "N")])


def test_station_alignment_recovers_a_linear_force() -> None:
    # Both sides ride the same station axis; the predicted force is ideal, so the
    # residual must be zero and the paired station must equal the observed stamps.
    time = np.linspace(0.0, 0.4, 41)
    observed = ObservationSet(
        (ChannelSpec("axle1_x_m", "m"), ChannelSpec("axle1_right_normal_n", "N")),
        time, np.array([10.0 + 100.0 * time, 60e3 + 2000.0 * time]), "s")
    shifted_time = np.linspace(0.01, 0.39, 30)
    predicted = ObservationSet(
        (ChannelSpec("axle1_x_m", "m"), ChannelSpec("axle1_right_normal_n", "N")),
        shifted_time,
        np.array([10.0 + 100.0 * shifted_time, 60e3 + 2000.0 * shifted_time]), "s")
    result = align(predicted, observed, "station")
    assert result.axis_unit == "m"
    assert result.samples > 20
    assert np.max(np.abs(result.residual[:, result.mask])) < 1e-6
    assert result.channel_metrics["axle1_right_normal_n"]["samples"] == result.samples


def test_station_alignment_does_not_extrapolate() -> None:
    time = np.linspace(0.0, 0.4, 41)
    station = 10.0 + 100.0 * time
    observed = ObservationSet(
        (ChannelSpec("axle1_x_m", "m"), ChannelSpec("axle1_right_normal_n", "N")),
        time, np.array([station, np.full_like(time, 1.0)]), "s")
    # Predicted covers only part of the observed run: 0.1 .. 0.2 s.
    part = np.linspace(0.1, 0.2, 11)
    predicted = ObservationSet(
        (ChannelSpec("axle1_x_m", "m"), ChannelSpec("axle1_right_normal_n", "N")),
        part, np.array([10.0 + 100.0 * part, np.ones(11)]), "s")
    result = align(predicted, observed, "station")
    assert result.samples == 11
    assert np.all(result.axis >= 20.0 - 1e-9)
    assert np.all(result.axis <= 30.0 + 1e-9)


def test_time_alignment_identical_series_is_zero() -> None:
    time = np.linspace(0.0, 0.1, 51)
    specs = (ChannelSpec("time_s", "s", role="check"),
             ChannelSpec("axle1_z_m", "m", sigma=1e-6))
    values = np.array([time, np.sin(2.0 * np.pi * 50.0 * time)])
    observed = ObservationSet(specs, time, values, "s")
    result = align(observed, observed, "time")
    assert result.samples == 51
    assert result.rms == pytest.approx(0.0, abs=1e-12)


def test_time_alignment_resamples_onto_requested_grid() -> None:
    dense = np.linspace(0.0, 0.2, 201)
    coarse = np.linspace(0.0, 0.2, 21)
    specs = (ChannelSpec("axle1_right_normal_n", "N", sigma=1.0),)
    predicted = ObservationSet(specs, dense, np.array([dense * 0.0 + 60e3]), "s")
    observed = ObservationSet(specs, coarse, np.array([coarse * 0.0 + 60e3]), "s")
    result = align(predicted, observed, "time", samples=41)
    assert result.samples == 41
    assert result.rms == pytest.approx(0.0, abs=1e-9)


def test_event_alignment_shifts_by_the_anchor_difference() -> None:
    # A unit pulse in time: predicted peaks at 0.30 s, measured at 0.34 s; after the
    # event shift both peaks coincide and the residual collapses.
    predicted_time = np.linspace(0.0, 0.6, 601)
    observed_time = np.linspace(0.0, 0.6, 301)
    specs = (ChannelSpec("acc_z_m_per_s2", "m/s^2", sigma=1.0),)
    predicted = ObservationSet(specs, predicted_time,
                               np.array([np.exp(-((predicted_time - 0.30) / 0.01) ** 2)]), "s")
    observed = ObservationSet(specs, observed_time,
                              np.array([np.exp(-((observed_time - 0.34) / 0.01) ** 2)]), "s")

    naive = align(predicted, observed, "time")
    shifted = align(predicted, observed, "event",
                    event_time_s=0.34, event_anchor_s=0.30)
    assert shifted.channel_metrics["acc_z_m_per_s2"]["max_abs"] < 0.05
    assert naive.channel_metrics["acc_z_m_per_s2"]["max_abs"] > shifted.channel_metrics[
        "acc_z_m_per_s2"]["max_abs"]
    with pytest.raises(ObservationError):
        align(predicted, observed, "event")
    with pytest.raises(ObservationError):
        align(predicted, observed, "time", event_time_s=0.34, event_anchor_s=0.30)


def test_sigma_weights_the_rms() -> None:
    time = np.linspace(0.0, 0.1, 11)
    specs = (ChannelSpec("axle1_right_normal_n", "N", sigma=1e3),
             ChannelSpec("axle2_right_normal_n", "N", sigma=1e4))
    observed = ObservationSet(specs, time,
                              np.array([np.full(11, 60e3), np.full(11, 60e3)]), "s")
    predicted = ObservationSet(specs, time,
                               np.array([np.full(11, 61e3), np.full(11, 60e3)]), "s")
    result = align(predicted, observed, "time")
    # One channel is off by 1000 N with sigma 1000 (z = 1), the other is exact.
    assert result.rms == pytest.approx(np.sqrt(0.5), rel=1e-6)


def test_observation_csv_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "measured.csv"
    time = np.linspace(0.0, 0.05, 11)
    path.write_text(
        "time_s,acc_z\n" + "\n".join(f"{t:.6f},{v:.6f}"
                                    for t, v in zip(time, np.linspace(1.0, 2.0, 11))),
        encoding="utf-8")
    specs = (ChannelSpec("acc_z", "m/s^2", sigma=0.5, role="check"),)
    observed = ObservationSet.from_csv(path, specs)
    assert observed.names == ("acc_z",)
    assert observed.values.shape == (1, 11)
    assert observed.provenance["source"].endswith("measured.csv")
    with pytest.raises(ObservationError):
        ObservationSet.from_csv(path, (ChannelSpec("missing", "m/s^2"),))


def test_observation_rejects_mismatched_channels_and_units() -> None:
    time = np.linspace(0.0, 0.1, 5)
    a = ObservationSet((ChannelSpec("axle1_z_m", "m"),), time, np.zeros((1, 5)), "s")
    b = ObservationSet((ChannelSpec("axle2_z_m", "m"),), time, np.zeros((1, 5)), "s")
    c = ObservationSet((ChannelSpec("axle1_z_m", "mm"),), time, np.zeros((1, 5)), "s")
    with pytest.raises(ObservationError):
        align(a, b, "time")
    with pytest.raises(ObservationError):
        align(a, c, "time")
    with pytest.raises(ObservationError):
        ChannelSpec("axle1_z_m", "m", role="prediction")
    with pytest.raises(ObservationError):
        ChannelSpec("axle1_z_m", "m", sigma=-1.0)
