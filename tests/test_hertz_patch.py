"""Checks for :mod:`velch.hertz_patch`.

The point of these tests is not that the numbers look plausible but that the implementation
reproduces the closed-form circular solution exactly, keeps the pressure identities, and lands in
the measured range for a real wheel/rail pair -- the patch a wear law will be integrated over.
"""

from __future__ import annotations

import math

import pytest

from velch.hertz_patch import (
    ellipticity_for,
    equivalent_modulus,
    hertz_patch,
    sphere_on_plane_patch,
)

FROZEN_FORCE_N = 59_680.5769
WHEEL_RADIUS_M = 0.43
STEEL_MODULUS = equivalent_modulus()


def test_the_circular_limit_reproduces_the_closed_form_sphere_solution():
    force = 59_680.5769
    radius = 0.43
    patch = sphere_on_plane_patch(force, radius_m=radius)
    expected = (3.0 * force * radius / (4.0 * STEEL_MODULUS)) ** (1.0 / 3.0)
    assert patch.semi_axis_a_m == pytest.approx(expected, rel=1.0e-9)
    assert patch.semi_axis_b_m == pytest.approx(expected, rel=1.0e-9)
    assert patch.ellipticity < 1.0e-6
    # Peak pressure of a circular Hertz contact: 3F / (2 pi a^2)
    assert patch.peak_pressure_pa == pytest.approx(3.0 * force / (2.0 * math.pi * expected**2), rel=1.0e-9)


def test_the_pressure_identities_hold_for_an_ellipse():
    patch = hertz_patch(FROZEN_FORCE_N, radius_x_m=WHEEL_RADIUS_M, radius_y_m=0.15)
    assert patch.area_m2 == pytest.approx(math.pi * patch.semi_axis_a_m * patch.semi_axis_b_m, rel=1.0e-12)
    assert patch.peak_pressure_pa == pytest.approx(1.5 * patch.mean_pressure_pa, rel=1.0e-12)
    assert patch.mean_pressure_pa == pytest.approx(patch.normal_force_n / patch.area_m2, rel=1.0e-12)


def test_a_real_wheel_rail_pair_lands_in_the_measured_patch_range():
    """A 60 kN wheel load gives 40-200 mm2 at 0.5-2.0 GPa -- the range quoted for tread contacts.

    The transverse radius is the crown radius (0.30 m each for wheel and rail, so 0.15 m
    equivalent); if a change makes this patch a point or a line, these bounds catch it.
    """
    patch = hertz_patch(FROZEN_FORCE_N, radius_x_m=WHEEL_RADIUS_M, radius_y_m=0.15)
    assert 40.0 <= patch.area_mm2 <= 200.0
    assert 0.5e9 <= patch.peak_pressure_pa <= 2.0e9
    assert 4.0 <= patch.semi_axis_a_mm <= 9.0
    assert 2.0 <= patch.semi_axis_b_mm <= 9.0
    assert patch.semi_axis_a_m >= patch.semi_axis_b_m


def test_the_ellipse_grows_flatter_as_the_curvature_difference_grows():
    flat = hertz_patch(FROZEN_FORCE_N, radius_x_m=0.43, radius_y_m=0.43)
    mild = hertz_patch(FROZEN_FORCE_N, radius_x_m=0.43, radius_y_m=0.20)
    sharp = hertz_patch(FROZEN_FORCE_N, radius_x_m=0.43, radius_y_m=0.02)
    assert flat.curvature_ratio < mild.curvature_ratio < sharp.curvature_ratio
    ratios = [
        p.semi_axis_a_m / p.semi_axis_b_m for p in (flat, mild, sharp)
    ]
    assert ratios[0] == pytest.approx(1.0, rel=1.0e-6)
    assert ratios[0] < ratios[1] < ratios[2]
    # Area *shrinks* as the transverse crown sharpens: the same load on a smaller ellipse.
    assert flat.area_m2 > mild.area_m2 > sharp.area_m2


def test_the_ellipticity_map_is_monotone_and_bounded():
    values = [ellipticity_for(f) for f in (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0)]
    assert values[0] < 1.0e-6
    assert values[-1] > 0.999
    assert values == sorted(values)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"normal_force_n": 0.0, "radius_x_m": 0.43, "radius_y_m": 0.15},
        {"normal_force_n": -1.0, "radius_x_m": 0.43, "radius_y_m": 0.15},
        {"normal_force_n": 1.0e4, "radius_x_m": 0.0, "radius_y_m": 0.15},
        {"normal_force_n": 1.0e4, "radius_x_m": 0.43, "radius_y_m": float("inf")},
    ],
)
def test_invalid_inputs_are_refused(kwargs):
    with pytest.raises(ValueError):
        hertz_patch(**kwargs)
