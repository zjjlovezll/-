"""The design line has one sign convention, and both forces are derived from it.

The curved route's history was three descriptions of "which way does the curve turn" that were
never bound to each other: the station table (``y = s^2/(2R)``, centre at ``+y``), the
equivalent-straight body force (``+m v^2/R`` towards ``+y`` under the comment "outward is +y"),
and the creep term ``-kappa v lever_y`` whose handedness was implicit.  Measured on R = 1100 m at
80 km/h, 0.34 s: the first pairing gave -78.1 % of ``m v^2/R`` and the other +69.1 %, and 0.60 s
then diverged to +157.2 % -- so one of the three had to become the reference.

``alignment.Alignment`` is that reference.  These tests pin the conventions it states, and the
one property that makes the fix safe: the legacy force route reproduces its archived arithmetic
exactly, so no frozen number moves.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.alignment import Alignment, alignment_for
from velch.paths import PathTrack

RADIUS_M = 1100.0
SPEED = 80.0 / 3.6
GRAVITY = 9.81


def _path_curving_to_plus_y(start_m: float = 30.0, length_m: float = 120.0,
                            step_m: float = 0.1, radius_m: float = RADIUS_M) -> PathTrack:
    stations = np.arange(start_m, start_m + length_m, step_m)
    offsets = np.maximum(stations - start_m, 0.0) ** 2 / (2.0 * radius_m)
    return PathTrack(tuple(float(s) for s in stations), tuple(float(y) for y in offsets))


def test_a_line_curving_towards_plus_y_has_positive_signed_curvature() -> None:
    line = Alignment.from_path(_path_curving_to_plus_y())
    assert line.has_line
    assert line.curvature_1_per_m == pytest.approx(1.0 / RADIUS_M, rel=1.0e-3)
    for station in (50.0, 80.0, 120.0):
        assert line.curvature_at(station) == pytest.approx(1.0 / RADIUS_M, rel=2.0e-3)


def test_the_inertia_force_points_away_from_the_centre() -> None:
    line = Alignment.from_path(_path_curving_to_plus_y())
    # Centre at +y, so the inertia force on the vehicle is towards -y.
    assert line.lateral_force_n(1000.0, SPEED, GRAVITY, 0.0) == pytest.approx(
        -1000.0 * SPEED * SPEED * line.curvature_at(0.0), rel=1.0e-9)
    assert line.lateral_force_n(1000.0, SPEED, GRAVITY, 0.0) < 0.0


def test_the_cant_term_points_towards_the_raised_rail_which_is_the_outside_one() -> None:
    line = Alignment.from_path(_path_curving_to_plus_y())
    # kappa > 0: the outside is -y and it is the raised one, so gravity pushes the body to +y.
    assert line.lateral_force_n(1000.0, 0.0, GRAVITY, 0.05) > 0.0
    # And with no cant the zero-speed force is zero -- creep is what steers a curve.
    assert line.lateral_force_n(1000.0, 0.0, GRAVITY, 0.0) == 0.0


def test_the_legacy_radius_route_keeps_its_archived_arithmetic_bit_for_bit() -> None:
    legacy = Alignment.from_radius(RADIUS_M)
    assert legacy.legacy_equivalent_straight and not legacy.has_line
    for mass, speed, sin_theta in ((48_654.0, SPEED, 0.0), (1_901.8, 27.7778, 0.0717),
                                   (48_654.0, 22.2222, -0.03)):
        expected = mass * (speed * speed / RADIUS_M - GRAVITY * sin_theta)
        assert legacy.lateral_force_n(mass, speed, GRAVITY, sin_theta) == expected


def test_a_straight_case_applies_no_lateral_force_at_all() -> None:
    straight = Alignment.straight()
    assert not straight.has_line and not straight.legacy_equivalent_straight
    assert straight.curvature_at(37.0) == 0.0
    assert straight.lateral_force_n(48_654.0, SPEED, GRAVITY, 0.0) == 0.0


def test_the_alignment_is_chosen_by_what_the_case_carries() -> None:
    class _Run:
        def __init__(self, radius):
            self.curve_radius_m = radius

    class _Case:
        def __init__(self, path, radius):
            self.path = path
            self.run = _Run(radius)

    line_case = _Case(_path_curving_to_plus_y(), RADIUS_M)
    assert alignment_for(line_case).has_line
    radius_only = _Case(None, RADIUS_M)
    assert alignment_for(radius_only).legacy_equivalent_straight
    assert alignment_for(_Case(None, None)).curvature_at(0.0) == 0.0


def test_a_path_with_a_corner_is_rejected_rather_than_averaged() -> None:
    with pytest.raises(ValueError):
        Alignment.from_path(PathTrack((0.0, 1.0, 2.0, 3.0), (0.0, math.nan, 0.0, 0.0)))
