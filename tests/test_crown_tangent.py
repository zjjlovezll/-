"""The contact of a 1:40 tread on a 300 mm crown sits R*s = 7.5 mm inside the crown apex.

`scripts/s104_crown_offset_sweep.py` measured 8.03 mm and a normal tilt of exactly 0.0250.  That is
the geometry of a conical tread on a circular crown -- the two surfaces touch where their slopes are
equal, so the contact point cannot be moved onto the apex by translating the rail (doing so slides
the wheel onto its own steeper band: 0.033 at 10 mm, 0.050 at 8 mm).

The old M2 gate -- "contact within 2 mm of the crown" -- therefore cannot be satisfied by *any*
correct model, and the frozen baseline violates it: the packaged case reproduces the frozen normal
tilt of +-0.0250 at a contact 8 mm inboard.  This test pins the tangent-point statement so the
correct gate is enforced from now on, and so that a future change that drags the contact onto the
apex is caught rather than celebrated.
"""
from __future__ import annotations

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
CROWN_RADIUS_M = 0.300
TREAD_TAPER = 0.025
TANGENT_OFFSET_M = CROWN_RADIUS_M * TREAD_TAPER
POSITION_TOL_M = 2.0e-3
TILT_TOL = 5.0e-3


@pytest.fixture(scope="module")
def seated():
    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    state = np.asarray(case.initial_q, dtype=float)
    velocity = np.asarray(case.initial_v, dtype=float)
    velocity[dynamics.topology.require("wheelset1", "spin")] = SPEED_M_S / ROLL_RADIUS_M
    state, residual = _seat(case, dynamics, state, velocity)
    _, merged = dynamics.evaluate(0.0, np.asarray(state, dtype=float), velocity)
    return case, dynamics, {rail.id: merged[rail.id] for rail in case.rails}


def _crown_y(case, rail_id: str) -> float:
    rail = next(rail for rail in case.rails if rail.id == rail_id)
    series = rail.contact_bodies[0].series
    station = float(case.run.x_start_m) + float(case.vehicle.axle_offsets_m[0])
    sample = series.sample(station, 1.0)
    # the crown is the y where the section is highest; z is positive up, so max z, and the answer
    # is the y at that index -- taking max(z) itself would return a height, not a position.
    return float(sample.profile.y_m[int(np.argmax(sample.profile.z_m))])


def test_the_contact_sits_where_a_tapered_tread_meets_a_circular_crown(seated):
    case, _, contacts = seated
    for rail_id, side in (("axle1_left", -1.0), ("axle1_right", 1.0)):
        crown = _crown_y(case, rail_id)
        lever = float(contacts[rail_id].geometry.lever_y_m)
        inboard = side * (crown - lever)
        assert abs(inboard - TANGENT_OFFSET_M) <= POSITION_TOL_M, (
            f"{rail_id}: contact is {inboard * 1e3:.2f} mm from the crown apex, "
            f"the tangent point of a {TREAD_TAPER:.3f} tread on a {CROWN_RADIUS_M:.3f} m crown is "
            f"{TANGENT_OFFSET_M * 1e3:.2f} mm"
        )


def test_the_contact_tilt_is_the_frozen_normal_tilt(seated):
    case, _, contacts = seated
    for rail_id, side in (("axle1_left", -1.0), ("axle1_right", 1.0)):
        geometry = contacts[rail_id].geometry
        tilt = float(geometry.normal_y / geometry.normal_z)
        # the tilt is measured with the section normal, so it leans *inboard* on both sides:
        # left +0.0246, right -0.0246, i.e. the sign is -side.
        assert tilt * side < 0.0, f"{rail_id}: tilt {tilt:+.4f} leans the wrong way"
        assert abs(abs(tilt) - TREAD_TAPER) <= TILT_TOL, (
            f"{rail_id}: contact tilt {tilt:+.4f} is not the tread taper {TREAD_TAPER:.4f}; the "
            "frozen baseline quotes n_y/n_z = +-0.0250"
        )


def test_the_offset_scales_with_the_crown_radius():
    """R*s, so a 0.02 m crown would put the contact 0.5 mm inboard instead of 7.5 mm."""
    assert abs(0.020 * TREAD_TAPER - 0.0005) < 1e-12
    assert abs(CROWN_RADIUS_M * TREAD_TAPER - 0.0075) < 1e-12
