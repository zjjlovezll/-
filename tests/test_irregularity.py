"""Tests for the ``.tre`` irregularity reader (no corpus needed)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.irregularity import (
    CHANNELS,
    IrregularityError,
    IrregularityTrack,
    dense_stations,
    rail_offsets,
    read_tre,
    window_factor,
    write_tre,
)


def _track(samples: int = 9, step: float = 0.25) -> IrregularityTrack:
    grid = np.arange(samples, dtype=float) * step
    return IrregularityTrack(
        s_m=grid,
        lateral_m=np.linspace(0.0, 1.0e-3, samples),
        vertical_m=np.full(samples, -2.0e-4),
        roll_rad=np.linspace(-1.0e-4, 1.0e-4, samples),
        gauge_m=np.full(samples, 5.0e-5),
        source="synthetic",
    )


def test_reading_a_written_file_gives_back_the_same_numbers(tmp_path):
    source = _track()
    target = write_tre(tmp_path / "rt.tre", source, comment="round trip")
    again = read_tre(target)
    assert len(again) == len(source)
    assert again.span_m == pytest.approx(source.span_m)
    for name in ("lateral_m", "vertical_m", "roll_rad", "gauge_m"):
        assert np.allclose(getattr(again, name), getattr(source, name), atol=1e-15)


def test_writing_twice_is_byte_identical(tmp_path):
    source = _track()
    first = write_tre(tmp_path / "a.tre", source)
    second = write_tre(tmp_path / "b.tre", source)
    assert first.read_bytes() == second.read_bytes()


def test_a_binary_file_is_refused_by_name_rather_than_guessed(tmp_path):
    binary = tmp_path / "simpack.tre"
    binary.write_bytes(b"\x00\x00\x00\x08" + bytes(64))
    with pytest.raises(IrregularityError, match="binary"):
        read_tre(binary)


def test_an_unsupported_data_type_says_which_one(tmp_path):
    path = tmp_path / "other.tre"
    path.write_text(
        "header.begin\n  data.type = 2\nheader.end\n0.0 0 0 0 0\n0.25 0 0 0 0\n",
        encoding="utf-8",
    )
    with pytest.raises(IrregularityError, match="data.type = 2"):
        read_tre(path)


def test_a_short_data_line_is_named_with_its_column_count(tmp_path):
    path = tmp_path / "short.tre"
    path.write_text(
        "header.begin\n  data.type = 1\nheader.end\n0.0 1e-4 2e-4\n0.25 0 0 0 0\n",
        encoding="utf-8",
    )
    with pytest.raises(IrregularityError, match="3 columns"):
        read_tre(path)


def test_unit_factors_are_applied(tmp_path):
    path = tmp_path / "mm.tre"
    path.write_text(
        "header.begin\n  data.type = 1\n  data.par(2) = 0.001\n  data.par(3) = 0.001\n"
        "header.end\n0.0 1.0 2.0 0.0 0.0\n0.25 1.0 2.0 0.0 0.0\n",
        encoding="utf-8",
    )
    track = read_tre(path)
    assert track.lateral_m[0] == pytest.approx(1.0e-3)
    assert track.vertical_m[1] == pytest.approx(2.0e-3)


def test_the_wavelength_band_is_stated_not_implied():
    track = _track(samples=4001, step=0.25)
    slow, fast = track.wavelength_band_m
    assert slow == pytest.approx(0.5)
    assert fast == pytest.approx(1000.0)
    assert track.describe()["note"]


def test_the_window_is_one_inside_and_zero_outside_with_a_smooth_fade():
    grid = np.array([0.0, 0.5, 1.0, 5.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0])
    factor = window_factor(grid, start_m=1.0, end_m=9.0, fade_m=2.0)
    assert factor[0] == pytest.approx(0.0)          # before the window
    assert factor[2] == pytest.approx(0.0)          # exactly at start: half-cosine starts at 0
    assert factor[3] == pytest.approx(1.0)          # well inside
    assert factor[4] == pytest.approx(0.5 - 0.5 * math.cos(math.pi * 0.75))  # fading down
    assert factor[5] == pytest.approx(0.5)          # one fade-length before the end
    assert factor[7] == pytest.approx(0.0)          # exactly at end: faded back to 0
    assert factor[8] == pytest.approx(0.0) and factor[9] == pytest.approx(0.0)


def test_the_window_refuses_an_empty_span():
    with pytest.raises(IrregularityError, match="empty"):
        window_factor(np.array([1.0]), start_m=5.0, end_m=2.0)


def test_roll_lifts_one_rail_and_drops_the_other():
    dy_left, dz_left = rail_offsets(0.0, 0.0, 1.0e-3, 0.0, half_gauge_m=0.7465, side="left")
    dy_right, dz_right = rail_offsets(0.0, 0.0, 1.0e-3, 0.0, half_gauge_m=0.7465, side="right")
    assert dz_left == pytest.approx(-0.7465e-3)
    assert dz_right == pytest.approx(+0.7465e-3)
    assert dy_left == pytest.approx(0.0) and dy_right == pytest.approx(0.0)


def test_gauge_widens_symmetrically_and_lateral_moves_both_rails():
    left = rail_offsets(2.0e-4, 0.0, 0.0, 1.0e-3, half_gauge_m=0.75, side="left")
    right = rail_offsets(2.0e-4, 0.0, 0.0, 1.0e-3, half_gauge_m=0.75, side="right")
    assert left[0] == pytest.approx(2.0e-4 - 0.5e-3)
    assert right[0] == pytest.approx(2.0e-4 + 0.5e-3)
    assert left[1] == pytest.approx(right[1])


def test_dense_stations_sample_the_grid_the_file_was_measured_on():
    track = _track(samples=41, step=0.25)
    rows = dense_stations(track, start_m=0.0, end_m=10.0, fade_m=0.0)
    assert len(rows) == 41
    assert rows[0][0] == pytest.approx(0.0)
    assert rows[-1][0] == pytest.approx(10.0)
    assert rows[0][2] == pytest.approx(-2.0e-4)


def test_a_window_that_misses_the_track_is_an_error():
    track = _track(samples=41, step=0.25)
    with pytest.raises(IrregularityError, match="does not overlap"):
        dense_stations(track, start_m=20.0, end_m=30.0)


def test_the_constructor_rejects_ragged_and_non_monotonic_input():
    with pytest.raises(IrregularityError, match="values"):
        IrregularityTrack(s_m=np.array([0.0, 1.0]), lateral_m=np.array([0.0]),
                          vertical_m=np.zeros(2), roll_rad=np.zeros(2), gauge_m=np.zeros(2))
    with pytest.raises(IrregularityError, match="strictly"):
        IrregularityTrack(s_m=np.array([0.0, 0.0]), lateral_m=np.zeros(2),
                          vertical_m=np.zeros(2), roll_rad=np.zeros(2), gauge_m=np.zeros(2))


def test_the_rms_is_reported_per_channel_in_millimetres():
    track = _track(samples=5)
    assert set(track.describe()["rms_mm"]) == set(CHANNELS)
    assert track.rms_mm("vertical") == pytest.approx(0.2, rel=1e-9)
    with pytest.raises(IrregularityError, match="unknown channel"):
        track.rms_mm("dinosaur")
