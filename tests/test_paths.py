"""The vehicle path decides which route a wheelset actually travels."""

from __future__ import annotations

import pytest

from velch.paths import PathError, PathTrack, load_path


def test_straight_outside_the_table() -> None:
    path = PathTrack((10.0, 20.0), (0.0, 0.1))
    assert path.at(0.0) == 0.0
    assert path.at(9.999) == 0.0
    assert path.at(30.0) == 0.0


def test_interpolates_inside_the_table() -> None:
    path = PathTrack((10.0, 20.0), (0.0, 0.1))
    assert path.at(10.0) == pytest.approx(0.0)
    assert path.at(15.0) == pytest.approx(0.05)
    assert path.at(20.0) == pytest.approx(0.1)


def test_slope_and_lateral_velocity() -> None:
    path = PathTrack((10.0, 20.0), (0.0, 0.1))
    assert path.slope_at(15.0) == pytest.approx(0.01)
    assert path.lateral_velocity_m_s(15.0, 97.2) == pytest.approx(0.972)
    assert path.slope_at(5.0) == 0.0
    assert path.slope_at(25.0) == 0.0


def test_span_and_summary() -> None:
    path = PathTrack((1.0, 2.0, 4.0), (0.0, 0.02, 0.02))
    assert path.span_m == (1.0, 4.0)
    assert "path 1.000..4.000 m" in path.summary()


def test_rejects_non_increasing_stations() -> None:
    with pytest.raises(PathError):
        PathTrack((1.0, 1.0), (0.0, 0.0))
    with pytest.raises(PathError):
        PathTrack((2.0, 1.0), (0.0, 0.0))


def test_rejects_mismatched_lengths_and_single_point() -> None:
    with pytest.raises(PathError):
        PathTrack((1.0, 2.0), (0.0,))
    with pytest.raises(PathError):
        PathTrack((1.0,), (0.0,))


def test_rejects_non_finite() -> None:
    with pytest.raises(PathError):
        PathTrack((1.0, 2.0), (0.0, float("nan")))


def test_load_path_forms() -> None:
    assert load_path(None) is None
    from_dict = load_path({"stations_s_m": [1.0, 2.0], "y_m": [0.0, 0.05]})
    from_pairs = load_path([[1.0, 0.0], [2.0, 0.05]])
    assert isinstance(from_dict, PathTrack) and isinstance(from_pairs, PathTrack)
    assert from_dict.at(1.5) == pytest.approx(from_pairs.at(1.5))
    with pytest.raises(PathError):
        load_path({"stations_s_m": [1.0, 2.0]})
    with pytest.raises(PathError):
        load_path("straight")


def test_offset_and_rate_are_consistent() -> None:
    """A wheel following the path moves laterally at speed*slope -- the creepage driver.

    Stations away from the knots only: at a knot the central difference straddles both segments and
    has no single slope, while ``slope_at`` deliberately returns the right-hand segment's value.
    """
    path = PathTrack((0.0, 6.0, 12.0), (0.0, 0.03, 0.09))
    speed = 97.2
    for station in (1.0, 3.0, 9.0):
        step = 1e-4
        numeric = (path.at(station + step) - path.at(station - step)) / (2 * step)
        assert path.lateral_velocity_m_s(station, speed) == pytest.approx(speed * numeric, rel=1e-6)
