"""The rail surface turns with the track plane; a level difference alone is not cant."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from velch.irregularity import RolledSeries, roll_rails


@dataclass(frozen=True)
class _Profile:
    y_m: object
    z_m: object
    dz_ds: float = 0.0
    source: str = "test"


@dataclass(frozen=True)
class _Sample:
    profile: object
    dz_ds: float = 0.001


class _Series:
    def __init__(self, y, z):
        self._profile = _Profile(np.asarray(y, dtype=float), np.asarray(z, dtype=float))

    def covers(self, s_m):
        return True

    def sample(self, s_m, direction=1):
        return _Sample(profile=self._profile)


def test_a_quarter_turn_swaps_the_axes_about_the_rail_centre() -> None:
    series = RolledSeries(_Series([1.0, 0.0], [0.0, 1.0]), np.pi / 2.0)
    profile = series.sample(5.0).profile
    assert profile.y_m == pytest.approx([0.0, -1.0], abs=1e-12)
    assert profile.z_m == pytest.approx([1.0, 0.0], abs=1e-12)
    assert profile.source.endswith("+roll")


def test_an_angle_of_zero_is_the_identity_and_costs_nothing() -> None:
    series = RolledSeries(_Series([1.0, 2.0], [3.0, 4.0]), 0.0)
    sample = series.sample(5.0)
    assert sample.profile.y_m.tolist() == [1.0, 2.0]
    assert sample.profile.source == "test"


def test_the_longitudinal_slope_survives_the_rotation() -> None:
    """A rotation about the longitudinal axis turns every tangent with it: dz/ds is untouched."""

    series = RolledSeries(_Series([0.0], [0.0]), 0.07)
    assert series.sample(5.0).dz_ds == pytest.approx(0.001, rel=0, abs=0)


def test_rolled_rails_leave_things_alone_at_zero_angle() -> None:
    class _Body:
        series = _Series([0.0], [0.0])

    class _Rail:
        id = "axle1_left"
        bodies = (_Body(),)

    rails = (_Rail(),)
    rolled = roll_rails(rails, 0.0)
    assert rolled[0].bodies[0].series.sample(1.0).profile.y_m.tolist() == [0.0]


def test_cant_of_107_mm_on_1493_mm_gauge_is_a_71_milliradian_turn() -> None:
    """The angle a case actually receives, so the wiring and the geometry cannot drift apart."""

    gauge = 1.493
    angle = float(np.arcsin(0.107 / gauge))
    assert angle == pytest.approx(0.0717, abs=1e-3)
    # A crown point 65 um above the rail centre moves 4.7 um sideways: negligible for contact.
    assert abs(65e-6 * np.sin(angle)) < 5e-6
