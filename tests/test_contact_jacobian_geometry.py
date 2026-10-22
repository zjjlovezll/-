"""Geometry of the contact Jacobian's position block.

The analytic Jacobian used to differentiate a *frozen* lever arm: the contact
station, the surface normal, the lever arms and the strip grid were all taken as
constants, so ``d(delta)/dq`` came out as the normal's own direction instead of the
gradient of the depth field.  On the 51-dof oracle case that made every wheelset
``y``/``z``/``roll`` column and every rail ``y``/``z`` column 4.4 % .. 6.9 % wrong
while a block-max tripwire saw nothing.

A strip ("strip_integral") contact is not a point contact: the normal force is a
*functional* of the whole depth field over the engaged band, so

* ``dN/dq`` is the band average of the depth gradient, not the gradient at the
  deepest strip -- about 6 % smaller on the full case, and
* the contact centroid, the lever arms, the normal direction and the longitudinal
  grade at the contact all move with ``q``.

These tests pin the published ``ContactPartials`` against a central difference of
the model's own contact geometry -- the finite difference is the ground truth.  The
pose is deliberately simple: a conical tread on a crowned rail, both sampled
densely, so the piecewise-linear interpolants have no slope staircase and the
difference quotient is exact to round-off.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.contact import find_strip_contact
from velch.profiles import GraphProfile, ProfileSample

#: Combined modulus used by the case this work was validated against.
E_STAR = 1.1393e11
WHEEL_CENTRE_Z = 0.430
CROWN_Y_M = 0.750
#: Lateral wheel offset of the test pose.  The posed band has to stay clear of the
#: sample bounds; a band that is cut off by a sample end has a moving-boundary term
#: this Jacobian deliberately does not model.
WHEEL_SHIFT_M = 4.0e-3
#: Tread cone.  Non-zero so the roll column's profile-slope term is not degenerate.
TREAD_SLOPE = 0.020


def _profile(y: np.ndarray, z: np.ndarray) -> GraphProfile:
    return GraphProfile(y_m=y, z_m=z, source_sha256="test", source="test")


def _sample(profile: GraphProfile) -> ProfileSample:
    return ProfileSample(profile=profile, dz_ds=np.zeros_like(profile.y_m),
                         lower_s_m=0.0, upper_s_m=1.0, selected_ids=("test",))


def _flat_wheel(half_span_m: float = 0.010) -> GraphProfile:
    y = np.linspace(CROWN_Y_M - half_span_m, CROWN_Y_M + half_span_m, 401)
    return _profile(y, np.full_like(y, -WHEEL_CENTRE_Z))


def _flat_rail(half_span_m: float = 0.012, height_m: float = 1.0e-4) -> GraphProfile:
    y = np.linspace(CROWN_Y_M - half_span_m, CROWN_Y_M + half_span_m, 481)
    return _profile(y, np.full_like(y, height_m))


def _conical_wheel(slope: float = TREAD_SLOPE, half_span_m: float = 0.020) -> GraphProfile:
    """A tread that is straight in its own frame: no slope staircase to confuse a FD."""
    y = np.linspace(CROWN_Y_M - half_span_m, CROWN_Y_M + half_span_m, 801)
    return _profile(y, -WHEEL_CENTRE_Z + slope * (y - CROWN_Y_M))


def _crowned_rail(radius_m: float = 0.15, half_span_m: float = 0.012) -> GraphProfile:
    """Narrower than the wheel, so the rail owns the strip grid and it does not move."""
    y = np.linspace(CROWN_Y_M - half_span_m, CROWN_Y_M + half_span_m, 801)
    return _profile(y, 1.0e-4 - (y - CROWN_Y_M) ** 2 / (2.0 * radius_m))


def _contact(offsets=(0.0, 0.0, 0.0, 0.0, 0.0), *, wheel=None, rail=None,
             wheel_y_m: float = WHEEL_SHIFT_M, wheel_z_m: float = WHEEL_CENTRE_Z,
             wheel_roll_rad: float = 0.0):
    """The strip contact for one rigid pose; ``offsets`` are in mode order.

    Mode order is ``(wheel_y, wheel_z, wheel_roll, rail_y, rail_z)``, the order
    ``ContactPartials`` publishes its tuples in.
    """
    wheel = _conical_wheel() if wheel is None else wheel
    rail = _crowned_rail() if rail is None else rail
    geometry = find_strip_contact(
        wheel, _sample(rail),
        wheel_y_m=wheel_y_m + offsets[0],
        wheel_z_m=wheel_z_m + offsets[1],
        wheel_roll_rad=wheel_roll_rad + offsets[2],
        wheel_lateral_offset_m=0.0,
        rail_y_m=offsets[3], rail_z_m=offsets[4],
        effective_modulus_pa=E_STAR,
        partials=True,
    )
    assert geometry is not None, "the test pose must keep the strip engaged"
    return geometry


def _elastic_force(geometry) -> float:
    return geometry.stiffness_n_m_1p5 * geometry.penetration_m ** 1.5


def test_vertical_shift_gradient_is_the_engaged_width() -> None:
    """On a flat-on-flat pose a unit lift removes exactly the engaged strip width.

    The band is a rectangle of ``2 * half_width`` at uniform depth, so
    ``dF/dz_w = -(pi/4) E * 2 * half_width`` exactly.
    """
    geometry = _contact(wheel=_flat_wheel(), rail=_flat_rail())
    width = 2.0 * geometry.half_width_m
    expected = -0.25 * math.pi * E_STAR * width
    published = geometry.partials.normal_force_n
    assert published[1] == pytest.approx(expected, rel=1.0e-10)
    # The rail carries the reaction: a unit rail lift is the exact opposite.
    assert published[4] == pytest.approx(-published[1], rel=1.0e-10)


@pytest.mark.parametrize("roll", [0.0, 2.0e-6])
def test_rail_z_gradient_is_the_negative_of_the_wheel_z_gradient(roll: float) -> None:
    """Lifting the rail by 1 and lowering the wheel by 1 are the same constraint."""
    published = _contact(wheel_roll_rad=roll).partials.normal_force_n
    assert published[1] < 0.0 < published[4]
    assert published[4] == pytest.approx(-published[1], rel=1.0e-12)


@pytest.mark.parametrize("roll", [0.0, 2.0e-6])
def test_roll_gradient_carries_the_profile_slope(roll: float) -> None:
    """The roll column is not the lever arm alone: the profile slope multiplies it.

    At a fixed lateral station a roll moves the wheel surface by
    ``(u + z z') / (c - s z')``, so ``d(delta)/d(roll)`` carries the profile slope
    ``z'`` times the vertical lever as well as the lateral lever.  The
    frozen-lever-arm form kept only ``n_y * l_z - n_z * l_y``.
    """
    geometry = _contact(wheel_roll_rad=roll)
    wheel = _conical_wheel()
    slope = float(np.interp(geometry.y_m, wheel.y_m,
                            np.gradient(wheel.z_m, wheel.y_m)))
    assert abs(slope) > 1.0e-3, "the pose must sit on the flank"

    published = geometry.partials.normal_force_n
    # Both columns are band sums over the same weights, so their ratio is the
    # (slope-weighted) mean lever arm: d(delta)/d(roll) / |d(delta)/d(z_w)|.
    ratio = published[2] / published[1]
    assert ratio == pytest.approx(geometry.lever_y_m + slope * geometry.lever_z_m,
                                  rel=5.0e-3)
    # The frozen form predicted the lever arm alone -- no profile-slope term at all.
    assert ratio != pytest.approx(geometry.lever_y_m, rel=5.0e-3)


@pytest.mark.parametrize("roll", [0.0, 2.0e-6])
def test_every_partial_reproduces_a_central_difference(roll: float) -> None:
    """Every published gradient is checked against a central difference."""
    centre = _contact(wheel_roll_rad=roll)
    published = centre.partials
    step = 1.0e-6
    for mode in range(5):
        offsets = [0.0] * 5
        offsets[mode] = step
        plus = _contact(tuple(offsets), wheel_roll_rad=roll)
        offsets[mode] = -step
        minus = _contact(tuple(offsets), wheel_roll_rad=roll)
        finite = (
            (_elastic_force(plus) - _elastic_force(minus)) / (2.0 * step),
            (plus.lever_y_m - minus.lever_y_m) / (2.0 * step),
            (plus.lever_z_m - minus.lever_z_m) / (2.0 * step),
        )
        columns = (published.normal_force_n, published.lever_y_m, published.lever_z_m)
        for index, (column, reference) in enumerate(zip(columns, finite)):
            # The lever arms are ratios of the band sums, so their central
            # difference is an order of magnitude noisier than the force's.
            tolerance = 1.0e-6 if index == 0 else 2.0e-4
            assert column[mode] == pytest.approx(reference, rel=tolerance,
                                                 abs=1.0e-9), (mode, index)
