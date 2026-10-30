"""The lateral force split is geometry, not the strip discretisation.

Round 243 measured dN/dp on the canonical case; this test pins the two facts that decide whether that
number can be quoted as physics at all:

  * refining ``strip_dy_m`` from 5e-4 to 1e-4 changes the split by less than 2 % -- so it is not the
    band integration (measured 0.05 %);
  * the seated penetration is the same at both widths to 0.1 um -- so the two runs are the same
    physical state and the comparison is like with like.

The analytic anchor is d(depth)/dp = s (the tread slope) for a cone on a circular crown, which for
s = 0.025 and dN/ddelta = 1.5 N / delta = 1417 kN/mm gives 35.4 kN/mm; the test bounds the measured
per-side values by that expression with a factor of two, because the LMA tread is not a pure cone.
"""
from __future__ import annotations

import dataclasses
import pathlib

import numpy as np
import pytest

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat

pytestmark = pytest.mark.corpus

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
SPEED_M_S = 80.0 / 3.6
ROLL_RADIUS_M = 0.43
TREAD_TAPER = 0.025
# 1.5 N / delta in N/m -> kN/mm is *1e-6; then times the tread slope (mm per mm).
ANALYTIC_KN_PER_MM = 1.5 * 60_153.0 / 63.70e-6 * 1e-6 * TREAD_TAPER
SPREAD_TOL = 0.02


def _split(strip_dy_m: float) -> tuple[float, float, float]:
    case = load_vehicle_case(CASE)
    case = dataclasses.replace(case, contact=dataclasses.replace(case.contact, strip_dy_m=strip_dy_m))
    dynamics = VehicleDynamics(case)
    state = np.asarray(case.initial_q, dtype=float)
    velocity = np.asarray(case.initial_v, dtype=float)
    velocity[dynamics.topology.require("wheelset1", "spin")] = SPEED_M_S / ROLL_RADIUS_M
    state, _ = _seat(case, dynamics, state, velocity)
    state = np.asarray(state, dtype=float)
    y_index = dynamics.topology.require("wheelset1", "y")

    forces = []
    penetration = None
    for shift_mm in (0.0, 1.0):
        q = state.copy()
        q[y_index] = state[y_index] + shift_mm * 1e-3
        _, merged = dynamics.evaluate(0.0, q, velocity)
        forces.append((float(merged["axle1_left"].normal_force_n),
                       float(merged["axle1_right"].normal_force_n)))
        if shift_mm == 0.0:
            bodies = [r for r in (dynamics.body_contacts.get("axle1_left") or ())
                      if r.active and r.geometry is not None]
            penetration = max(r.geometry.penetration_m for r in bodies)
    left = (forces[1][0] - forces[0][0]) / 1e3
    right = (forces[1][1] - forces[0][1]) / 1e3
    return left, right, float(penetration)


def test_refining_the_strip_leaves_the_force_split_alone():
    coarse = _split(5.0e-4)
    fine = _split(1.0e-4)
    for name, index in (("left", 0), ("right", 1)):
        delta = abs(fine[index] - coarse[index])
        assert delta <= SPREAD_TOL * abs(fine[index]), (
            f"dN/dy {name} moved {delta:.3f} kN/mm ({delta / abs(fine[index]) * 100:.2f} %) between "
            f"strip_dy 5e-4 and 1e-4; if the impedance is band-limited it cannot be quoted as geometry"
        )
    assert abs(fine[2] - coarse[2]) <= 1e-7, (
        f"seated penetration differs by {(fine[2] - coarse[2]) * 1e6:.3f} um between strip widths, so "
        "the two runs are not the same physical state"
    )


def test_the_split_matches_the_analytic_taper_slope_within_a_factor_of_two():
    left, right, _ = _split(5.0e-4)
    for name, value in (("left", left), ("right", right)):
        assert 0.5 * ANALYTIC_KN_PER_MM <= abs(value) <= 2.0 * ANALYTIC_KN_PER_MM, (
            f"dN/dy {name} = {value:+.2f} kN/mm is outside 0.5-2.0x the analytic "
            f"1.5N/delta * s = {ANALYTIC_KN_PER_MM:.1f} kN/mm"
        )
    assert left < 0.0 < right, (
        f"the split must be antisymmetric in sign (left {left:+.2f}, right {right:+.2f}): a lateral "
        "shift unloads one side and loads the other"
    )
