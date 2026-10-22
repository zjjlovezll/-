"""The saturated creep law's derivatives.

These tests exist because the assembled-Jacobian tripwire normalises each block by its
largest entry: a column wrong by 100 % then reads as a few percent, and a column wrong
by a factor of ``ratio`` passes whenever that ratio happens to be one.

The law is four lines and piecewise smooth, so the two partials are compared against an
**independent re-derivation** of the composite function rather than against finite
differences -- ``T`` saturates to a flat plateau, where a difference quotient is all
cancellation noise, and the interesting branch boundary sits right next to it.
"""

from __future__ import annotations

import inspect
import types

import pytest

from velch.jacobian import JacobianAssembler

K_OVER_V = 1.0e6 / 97.222
MU = 0.4


class _Law:
    friction_coefficient = MU
    creep_stiffness_x_n = 1.0e6
    creep_stiffness_lateral_n = 5.0e5


class _Assembler:
    """Only the two attributes ``_creep_slopes`` reads."""

    law = _Law()
    reference_speed = 97.222


def _response(slip_x: float, slip_lat: float = 0.0) -> types.SimpleNamespace:
    return types.SimpleNamespace(slip_x_m_s=slip_x, slip_lateral_m_s=slip_lat)


def _shape(ratio: float) -> float:
    """The cubic saturation profile, in the literature's normalised form."""
    if ratio <= 3.0:
        return ratio - ratio * ratio / 3.0 + ratio ** 3 / 27.0
    return 1.0


def _dshape(ratio: float) -> float:
    """``d(shape)/d(ratio)``."""
    if ratio <= 3.0:
        return 1.0 - 2.0 * ratio / 3.0 + ratio * ratio / 9.0
    return 0.0


def _reference_partials(normal_force: float, slip_x: float) -> tuple[float, float, float]:
    """``(scale, d scale/d demand, d scale/d limit)`` derived by hand.

    ``scale = limit * shape(ratio) / demand`` with ``ratio = demand / limit``; at fixed
    slip a change of the normal force changes ``limit`` only, and
    ``d(ratio)/d(limit) = -ratio/limit``, hence

        d scale/d limit = (shape - ratio * dshape) / demand

    where ``demand`` -- not ``limit`` -- is the denominator.
    """
    demand = abs(K_OVER_V * slip_x)
    limit = MU * normal_force
    ratio = demand / limit
    shape = _shape(ratio)
    dshape = _dshape(ratio)
    scale = limit * shape / demand
    d_demand = (dshape - scale) / demand
    d_limit = (shape - ratio * dshape) / demand
    return scale, d_demand, d_limit


@pytest.mark.parametrize("ratio", [0.01, 0.2, 0.5, 1.0, 2.0, 2.99, 3.0, 5.0, 40.0])
def test_scale_partials_match_the_hand_derivation(ratio: float) -> None:
    """Both partials, on both branches and at the branch boundary."""
    assembler = _Assembler()
    normal_force = 60_000.0
    demand = ratio * MU * normal_force
    slip_x = -demand / K_OVER_V

    scale, d_demand, d_limit = JacobianAssembler._creep_slopes(
        assembler, _response(slip_x), normal_force)[2:]

    scale_ref, d_demand_ref, d_limit_ref = _reference_partials(normal_force, slip_x)
    assert scale == pytest.approx(scale_ref, rel=1.0e-12), ratio
    assert d_demand == pytest.approx(d_demand_ref, rel=1.0e-12), ratio
    assert d_limit == pytest.approx(d_limit_ref, rel=1.0e-12), ratio


@pytest.mark.parametrize("ratio", [5.0, 40.0])
def test_saturated_branch_is_closed_form(ratio: float) -> None:
    """Saturated: ``d scale/d demand = -scale/demand`` and ``d scale/d limit = 1/demand``.

    The second one is the tripwire for the denominator: dividing by ``limit`` instead
    of ``demand`` is off by exactly ``ratio``, invisible at ``ratio = 1``.
    """
    assembler = _Assembler()
    normal_force = 60_000.0
    limit = MU * normal_force
    demand = ratio * limit
    slip_x = -demand / K_OVER_V

    scale, d_demand, d_limit = JacobianAssembler._creep_slopes(
        assembler, _response(slip_x), normal_force)[2:]

    assert scale == pytest.approx(limit / demand)
    assert d_demand == pytest.approx(-scale / demand, rel=1.0e-12)
    assert d_limit == pytest.approx(1.0 / demand, rel=1.0e-12)


def test_zero_demand_keeps_the_creep_stiffness() -> None:
    """Free rolling must not delete the creep stiffness.

    The cubic's limit as the demand vanishes is ``scale -> 1``; returning zero there
    removes ``k/V`` from the tangential block exactly at pure rolling, which makes the
    Newton matrix singular (the integrator answers by shrinking its step, silently).
    """
    assembler = _Assembler()
    linear_x, linear_lat, scale, d_demand, d_limit = JacobianAssembler._creep_slopes(
        assembler, _response(0.0), 60_000.0)
    assert scale == pytest.approx(1.0)
    assert (d_demand, d_limit) == (0.0, 0.0)
    assert linear_x == 0.0 and linear_lat == 0.0
    tiny = JacobianAssembler._creep_slopes(assembler, _response(1.0e-12), 60_000.0)[2]
    assert tiny == pytest.approx(1.0, rel=1.0e-6)


def test_negative_normal_force_has_no_tangential_force() -> None:
    """A separated patch (``N = 0``) carries no friction and no friction slope."""
    assembler = _Assembler()
    linear_x, linear_lat, scale, d_demand, d_limit = JacobianAssembler._creep_slopes(
        assembler, _response(1.0e-3), 0.0)
    assert (scale, d_demand, d_limit) == (0.0, 0.0, 0.0)
    assert linear_x != 0.0 and linear_lat == 0.0


def test_spin_column_is_a_velocity_coupling() -> None:
    """``dT_x/d(spin rate)`` is nonzero and the term lives in ``Jv``.

    ``slip_x = travel + spin * lever_z`` with ``spin`` a velocity coordinate, so the
    chain rule puts the column in ``d(f/m)/dv``.  Writing it to ``dq`` produced a
    spurious stiffness term and left the real velocity coupling at zero; the block-max
    tripwire could not see either.  The placement is guarded structurally, the
    magnitude against the hand derivation.
    """
    assembler = _Assembler()
    normal_force = 60_000.0
    slip_x = 0.5 * MU * normal_force / K_OVER_V
    lever_z = 0.35

    scale, d_demand = JacobianAssembler._creep_slopes(
        assembler, _response(slip_x), normal_force)[2:4]
    linear_x = -K_OVER_V * slip_x
    gain_x = scale + linear_x * linear_x * d_demand / abs(linear_x)
    d_t_x_d_slip = gain_x * (-K_OVER_V)

    # The force slope the code implies, from the hand-derived partials.
    scale_ref, d_demand_ref, _ = _reference_partials(normal_force, slip_x)
    assert scale == pytest.approx(scale_ref, rel=1.0e-12)
    assert gain_x == pytest.approx(scale_ref + abs(linear_x) * d_demand_ref, rel=1.0e-12)
    assert lever_z * d_t_x_d_slip != 0.0

    source = inspect.getsource(JacobianAssembler)
    assert "longitudinal_v[wheel + 3]" in source
    assert "longitudinal_q" not in source
