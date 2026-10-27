"""A vehicle set on the design line must also be given the line's own lateral velocity (B043).

``_align_to_track_frame`` puts the vehicle *on* the line; it used to leave it with zero lateral
velocity while the rail surface at the same mileage moves at ``v * dy/ds``.  Measured on the geometry
route (R = 1100 m, 80 km/h): the run tracked the straight and the guard clipped it 1.04 m into a
0.34 s acceptance gate.

Two behaviours are pinned here, both of them measured facts about the code rather than preferences:

* ``_align_velocity_to_track`` gives each body exactly ``local_state``'s third return value -- the
  placement's analytic ``speed * dy_ds``.  A differenced slope is *not* the same number: on a
  quadratic, a one-metre forward difference lags the tangent by half a metre and reported
  0.2121 m/s where the rail moves at 0.2020 m/s, and that 5 % outward creep is then paid off by a
  saturated patch for the whole run.
* ``_align_to_track_frame`` writes ``yaw = 0``, not the line's tangent: the state ``yaw`` is read by
  the creep law as an angle of attack (``travel * q[yaw]``), so the tangent injects
  ``travel * arctan(slope)`` of spurious lateral creep -- 0.352 m/s at 30 m, 0.6707 m/s at 81.6 m.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import (
    VehicleDynamics,
    _align_to_track_frame,
    _align_velocity_to_track,
    _place_on_alignment,
    _seat,
)

pytestmark = pytest.mark.corpus

SPEED_KMH = 80.0
RADIUS_M = 1100.0


def _curved_case(tmp_path, *, geometry: bool):
    raw = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
    raw.pop("initial_state", None)
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw["run"].update({
        "x_start_m": 30.0,
        "seat_x_start_m": 30.0,
        "duration_s": 0.005,
        "output_step_s": 0.005,
        "curve_radius_m": RADIUS_M,
        "curve_geometry": geometry,
        "align_to_track": geometry,
    })
    path = tmp_path / f"curve_{'geometry' if geometry else 'force'}.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return load_vehicle_case(path)


def _seated_and_placed(case):
    dynamics = VehicleDynamics(case)
    velocity = np.zeros(dynamics.dimension)
    speed = float(case.vehicle.travel_speed_m_s)
    radius = float(case.vehicle.nominal_wheel_radius_m)
    for body in dynamics.topology.wheelsets():
        velocity[dynamics.topology.require(body.id, "spin")] = speed / radius
    seated, residual = _seat(case, dynamics, np.zeros(dynamics.dimension), velocity)
    assert residual < 1e-5
    placed = _align_to_track_frame(case, dynamics, _place_on_alignment(case, dynamics, seated))
    return case, dynamics, placed, velocity


def test_the_initial_lateral_velocity_is_the_placements_own_derivative(tmp_path):
    case, dynamics, placed, velocity = _seated_and_placed(_curved_case(tmp_path, geometry=True))
    aligned = _align_velocity_to_track(case, dynamics, placed, velocity)
    topology = dynamics.topology
    start = float(case.run.x_start_m)
    speed = float(case.vehicle.travel_speed_m_s)
    zeros = np.zeros(len(placed))
    checked = 0
    for axle, body in enumerate(topology.wheelsets()):
        row = topology.require(body.id, "y")
        mileage = start + float(case.vehicle.axle_offsets_m[axle])
        expected = dynamics.track.local_state(zeros, zeros, axle, mileage, speed)[2]
        assert abs(expected) > 1e-3, "this test is vacuous unless the rail really moves"
        assert aligned[row] == pytest.approx(expected, rel=1e-12, abs=1e-15)
        checked += 1
    assert checked == 4
    # The differenced slope would have been 5 % high at the first axle; pin the difference.
    gauge, _ = __import__("velch.vehicle_solver", fromlist=["_gauge_centre"])._gauge_centre(
        case, start + float(case.vehicle.axle_offsets_m[0]), dynamics, abs(speed))
    assert abs(speed * gauge) > abs(aligned[topology.require(topology.wheelset_id(0), "y")])


def test_the_alignment_writes_no_heading_into_the_attack_coordinate(tmp_path):
    case, dynamics, placed, _velocity = _seated_and_placed(_curved_case(tmp_path, geometry=True))
    topology = dynamics.topology
    for body in topology.bodies:
        if "yaw" in body.dof:
            assert placed[topology.require(body.id, "yaw")] == 0.0
    # And the vehicle really is off the origin, so the zero is a decision, not an empty alignment.
    assert any(abs(placed[topology.require(body.id, "y")]) > 1e-3
               for body in topology.wheelsets())


def test_the_force_route_gets_no_lateral_velocity_for_the_line_it_does_not_have(tmp_path):
    case, dynamics, placed, velocity = _seated_and_placed(_curved_case(tmp_path, geometry=False))
    before = np.array(velocity, dtype=float)
    after = _align_velocity_to_track(case, dynamics, placed, before)
    assert np.array_equal(before, after)
