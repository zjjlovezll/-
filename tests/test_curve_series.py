"""The circular alignment as a property of the rail series.

A rigid track kernel has no placement hook, so a geometric curve on a 35-coordinate case moved the
vehicle onto the arc while the rails stayed straight; the wheels then sat 45.5 mm beside their rails
and the contact rows carried 1.95 MN.  ``CurveSeries`` publishes ``y(s) = s^2/(2R)`` where every
consumer already looks (the sampled profile).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import json

import numpy as np
import pytest

from velch.irregularity import CurveSeries, RolledSeries


@dataclass(frozen=True)
class _Profile:
    """Minimal stand-in for ``velch.profiles.Profile`` (``replace`` needs a dataclass)."""

    y_m: np.ndarray
    z_m: np.ndarray
    source: str = "stub"


@dataclass(frozen=True)
class _Sample:
    profile: _Profile
    dz_ds: float = 0.0


class _Series:
    """A flat straight rail: one sample regardless of mileage."""

    def __init__(self):
        self.profile = _Profile(np.array([-0.7896, -0.7465, -0.71]),
                                np.array([-0.0299, 0.0, -0.0001]))

    def covers(self, s_m):
        return True

    def sample(self, s_m, direction=1):
        return _Sample(self.profile, 0.0)


def test_the_lateral_offset_is_the_arc_sagitta():
    straight = _Series()
    curved = CurveSeries(straight, radius_m=1100.0, origin_m=60.0, side=1)
    base = float(straight.sample(60.0).profile.y_m[0])
    for offset in (0.0, 10.0, 20.0):
        sampled = curved.sample(60.0 + offset)
        assert float(sampled.profile.y_m[0]) - base == pytest.approx(offset * offset / 2200.0,
                                                                    abs=1e-15)


def test_the_height_is_untouched_without_cant():
    straight = _Series()
    curved = CurveSeries(straight, radius_m=1100.0, origin_m=60.0, side=1)
    sampled = curved.sample(80.0)
    assert np.array_equal(np.asarray(sampled.profile.z_m), np.asarray(straight.profile.z_m))
    assert float(sampled.dz_ds) == 0.0


def test_cant_raises_the_outer_rail_by_half_the_gauge_times_sine():
    half_gauge = 0.7465
    cant = 0.107
    angle = math.asin(cant / (2.0 * half_gauge))
    rise = 0.5 * 2.0 * half_gauge * math.sin(angle)
    outer = CurveSeries(_Series(), radius_m=1100.0, origin_m=60.0, side=1, cant_m=cant,
                        half_gauge_m=half_gauge)
    inner = CurveSeries(_Series(), radius_m=1100.0, origin_m=60.0, side=-1, cant_m=cant,
                        half_gauge_m=half_gauge)
    base = float(_Series().sample(61.0).profile.z_m[0])
    assert float(outer.sample(61.0).profile.z_m[0]) - base == pytest.approx(rise, abs=1e-12)
    assert float(inner.sample(61.0).profile.z_m[0]) - base == pytest.approx(-rise, abs=1e-12)


def test_coverage_follows_the_wrapped_series():
    curved = CurveSeries(_Series(), radius_m=1100.0, origin_m=60.0, side=1)
    assert bool(curved.covers(12.5)) is True


def test_the_source_says_the_sample_is_curved():
    curved = CurveSeries(_Series(), radius_m=1100.0, origin_m=60.0, side=1)
    assert curved.sample(61.0).profile.source.endswith("+curve")


def test_a_roll_and_a_curve_compose_without_changing_the_radius():
    rolled = RolledSeries(_Series(), angle_rad=0.0717)
    curved = CurveSeries(rolled, radius_m=1100.0, origin_m=60.0, side=1)
    base = float(rolled.sample(80.0).profile.y_m[0])
    sampled = curved.sample(80.0)
    # The rotation moves a point at y = 0.75 m by about 54 mm, and the arc adds its own 182 mm.
    assert float(sampled.profile.y_m[0]) - base == pytest.approx(20.0 * 20.0 / 2200.0, abs=1e-9)
