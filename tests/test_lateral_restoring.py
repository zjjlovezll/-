"""The lateral budget of the seated curve, pinned as arithmetic.

Round 206 measured the lateral response of the seated ``cant = 0.060 m`` curve: moving the whole
vehicle 1 mm towards +y changes the left-minus-right load by 240 kN and the net lateral force by
5.4 kN.  Three consequences are checked here as arithmetic on those numbers, because each of them is
something a later change could silently invalidate:

1. the in-band lateral ceiling (8 169.6 N, measured in round 204) *is* ``0.0210 * W`` -- the frozen
   contact angle times the weight -- so the ceiling is a load-transfer bound and not a creep bound;
2. that bound (10.03 kN) is below the 21 842.4 N a cant-free curve needs, which is why the 18-turnout
   diverging route cannot stand in band without cant;
3. the restoring the model offers (5.40 MN/m) is three orders stiffer than Wickens' gravitational
   stiffness (5.83 kN/m), i.e. B047: the vehicle is located by a 65.47 um Hertz penetration rather
   than by conicity and creep;
4. therefore the round-205 excursion at 1.0 s (+152 849 N of transfer) is a walk of 0.64 mm -- no
   runaway, just a sub-millimetre position error leaving a sub-millimetre window.

Every constant below is a measurement recorded in ``docs/CURVE_LATERAL_RESTORING_2026-10-28.md`` with
the command that produced it; the tests exist so that the *implication* of those numbers cannot be
quietly broken by a change elsewhere.
"""

from __future__ import annotations

import pytest

WEIGHT_N = 477_295.7
EVEN_SHARE_N = 59_662.0
DEMAND_CANT_FREE_N = 21_842.4
DEMAND_CANT_60MM_N = 2_662.0
CONTACT_TILT = 0.0210
MEASURED_IN_BAND_CEILING_N = 8_169.6
MEASURED_K_FORCE_N_PER_M = 5.4045e6
MEASURED_K_TRANSFER_N_PER_M = 239_712_190.0  # printed as 239 712 kN/m; 240 kN per millimetre
ROUND_205_TRANSFER_N = 152_849.0
NOMINAL_RADIUS_M = 0.43
WHEELSETS = 4


def gravitational_stiffness_n_per_m() -> float:
    """Wickens: one wheelset's lateral stiffness is ``W/n * lambda / r``."""

    return (WEIGHT_N / WHEELSETS) * CONTACT_TILT / NOMINAL_RADIUS_M


def test_the_in_band_ceiling_is_the_load_transfer_bound() -> None:
    bound = CONTACT_TILT * WEIGHT_N
    assert bound == pytest.approx(10_023.2, rel=1e-3)
    # The measured 8 169.6 N ceiling sits at 81 % of that bound: two independent measurements of the
    # same thing, which is what makes the diagnosis "load transfer, not creep" hold.
    assert 0.75 < MEASURED_IN_BAND_CEILING_N / bound < 0.90
    # And the bound is below what a cant-free curve needs, so no offset can satisfy it.
    assert bound < DEMAND_CANT_FREE_N
    assert MEASURED_IN_BAND_CEILING_N / DEMAND_CANT_FREE_N == pytest.approx(0.374, abs=5e-3)


def test_the_curve_needs_less_than_the_bound_once_the_cant_is_in_the_frame() -> None:
    # cant 0.060 m takes the requirement from 21 842.4 N to 2 662 N, which is inside the 10.0 kN
    # bound -- the reason round 205 could stand the curve in band at all.
    assert DEMAND_CANT_60MM_N < CONTACT_TILT * WEIGHT_N
    assert DEMAND_CANT_60MM_N / DEMAND_CANT_FREE_N == pytest.approx(0.122, abs=2e-3)


def test_the_model_restores_three_orders_stiffer_than_a_real_wheelset() -> None:
    k_grav = gravitational_stiffness_n_per_m()
    assert k_grav == pytest.approx(5_828.6, rel=5e-3)
    ratio = MEASURED_K_FORCE_N_PER_M / k_grav
    assert 800.0 < ratio < 1_100.0, f"restoring ratio {ratio:.1f} left the measured band"
    # Positive restoring: the response opposes the shift.  This is the pre-registered
    # RESTORING STIFF branch, not RESTORING BLIND -- round 205's hypothesis is refuted.
    assert MEASURED_K_FORCE_N_PER_M > 0.0


def test_the_one_second_excursion_is_a_sub_millimetre_walk() -> None:
    walk_mm = ROUND_205_TRANSFER_N / MEASURED_K_TRANSFER_N_PER_M * 1e3
    assert 0.5 < walk_mm < 0.75, f"excursion corresponds to {walk_mm:.3f} mm of lateral walk"
    # Two millimetres of walk moves essentially the whole weight, which is why the acceptance band
    # is a sub-millimetre window and not a force question.
    assert MEASURED_K_TRANSFER_N_PER_M * 2.0e-3 > 0.9 * WEIGHT_N
    assert EVEN_SHARE_N * 8 == pytest.approx(WEIGHT_N, rel=1e-6)
