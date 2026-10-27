"""A curve needs two things at once: the lateral unknowns to seat on it, and curvature in the creep.

The equivalent-straight track adds ``m v^2 / R`` while the rails stay straight, so the only way the
solved state could balance that force was for the wheels to walk into the flange — measured as
``graph slope limit at axle1_left/left, x=70 m`` at the very first step, i.e. the seat had already
put the wheel there.  Two changes fix it and each is pinned here:

* the static equilibrium widens its unknowns from ``z`` to ``y`` and ``roll`` when the run has a
  curve, so the seat can answer the lateral question the equations actually ask;
* the longitudinal creep carries ``-kappa v b`` per contact, so the two contacts of one axle travel
  different arc lengths and the wheelset can steer instead of rubbing on the flange.

The 1.0 slope guard is *not* loosened: an unbalanced curve (R = 1100 m with no cant at 100 km/h,
where the theoretical cant is 0.107 m) still trips it, because riding the flange there is what a
straight-railed model would really do.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _load_per_wheel, simulate_vehicle

pytestmark = pytest.mark.corpus

REPO = pathlib.Path(__file__).resolve().parents[1]
BASE = None


def _base_path() -> pathlib.Path:
    """The inline 35-coordinate straight case from the validation corpus."""

    global BASE
    if BASE is None:
        from velch import data_root

        BASE = data_root.case_dir() / "case_A_final_law.json"
    return BASE


def _case(tmp_path: pathlib.Path, name: str, *, radius: float, cant: float,
          speed_kmh: float, duration_s: float = 0.01) -> pathlib.Path:
    raw = json.loads(_base_path().read_text(encoding="utf-8"))
    raw["run"].update({"x_start_m": 60.0, "duration_s": duration_s,
                       "output_step_s": duration_s})
    if radius is not None:
        raw["run"]["curve_radius_m"] = float(radius)
        raw["run"]["curve_cant_m"] = float(cant)
    raw["vehicle"]["travel_speed_m_s"] = speed_kmh / 3.6
    raw.pop("initial_state", None)
    raw["case_id"] = f"curve_{name}"
    target = tmp_path / f"case_{name}.json"
    target.write_text(json.dumps(raw, indent=1, ensure_ascii=False), encoding="utf-8")
    return target


def test_a_straight_case_carries_no_curvature(tmp_path):
    path = _case(tmp_path, "straight", radius=None, cant=0.0, speed_kmh=100.0)
    dynamics = VehicleDynamics(load_vehicle_case(path), contact_workers=1)
    assert dynamics._curvature_1_per_m == 0.0


def test_a_curved_case_carries_one_over_radius(tmp_path):
    dynamics = VehicleDynamics(
        load_vehicle_case(_case(tmp_path, "r1100", radius=1100.0, cant=0.0, speed_kmh=100.0)),
        contact_workers=1)
    assert dynamics._curvature_1_per_m == pytest.approx(1.0 / 1100.0)


def test_the_curvature_enters_the_longitudinal_slip_with_opposite_sign_per_side():
    """The term is ``-kappa v b``: the outer contact (larger ``b``) gets the more negative slip."""

    from velch.contact import evaluate_contact
    from velch.vehicle import load_vehicle_case as load

    case = load(_base_path())
    law = case.contact
    dynamics = VehicleDynamics(case, contact_workers=1)
    q = np.zeros(dynamics.dimension)
    v = np.zeros(dynamics.dimension)
    # A seated state is needed before any contact geometry exists: at q = 0 nothing is in
    # penetration, so the wheel has not touched the rail yet.
    for body in dynamics.topology.wheelsets():
        q[dynamics.topology.require(body.id, "z")] = -1.0e-3
    _, contacts = dynamics.evaluate(0.0, q, v)
    geometry = next(item.geometry for item in contacts.values() if item.geometry is not None)

    def slip(curvature: float) -> float:
        response = evaluate_contact(
            geometry, law, wheel_v_y_m_s=0.0, wheel_v_z_m_s=0.0, wheel_roll_rate_rad_s=0.0,
            wheel_spin_rate_rad_s=0.0, rail_v_y_m_s=0.0, rail_v_z_m_s=0.0,
            travel_speed_m_s=27.7778, curvature_1_per_m=curvature)
        return response.slip_x_m_s

    straight = slip(0.0)
    curved = slip(1.0 / 400.0)
    expected = -27.7778 * geometry.lever_y_m / 400.0
    assert curved - straight == pytest.approx(expected, rel=1e-12, abs=1e-15)
    assert expected != 0.0


def test_a_balanced_curve_seats_eight_wheels_and_runs(tmp_path):
    path = _case(tmp_path, "balanced", radius=1100.0, cant=0.107, speed_kmh=100.0)
    case = load_vehicle_case(path)
    result = simulate_vehicle(case)
    assert result.summary["result_status"] == "numerically_checked"
    assert all(result.summary["gates"].values())
    loads = [result.contacts[-1][rail.id].normal_force_n for rail in case.rails]
    per_wheel = _load_per_wheel(case.rails, loads)
    from velch.topology import topology_for

    topology = topology_for(case)
    even = sum(body.mass_kg for body in topology.bodies) * case.vehicle.gravity_m_s2 / 8.0
    assert len(per_wheel) == 8
    for value in per_wheel.values():
        assert 0.5 * even <= value <= 1.6 * even


def test_an_unbalanced_curve_still_trips_the_slope_guard(tmp_path):
    from velch.solver import SimulationFailure

    path = _case(tmp_path, "unbalanced", radius=1100.0, cant=0.0, speed_kmh=100.0)
    with pytest.raises(SimulationFailure, match="graph slope limit"):
        simulate_vehicle(load_vehicle_case(path))


def test_the_curved_seat_does_not_answer_the_yaw_question(tmp_path):
    """Yaw stays an initial condition, not a seat unknown.

    Letting the seat solve yaw looked attractive — the rails of a curved station table are already
    turned while the vehicle stands at zero yaw — but it is the wrong lever: a solved yaw branch can
    satisfy every load criterion and still leave the wheels rotated against the track, and the run
    then dies at ``graph slope limit at axle3_left/left:main, x=52.5 m`` *after* a seat that looked
    balanced.  A rigid yaw offset cannot repair it either: over the 20 m footprint at R = 1100 m the
    tangent differs by 18 mrad front to rear, so a sweep of 0, ±2, ±5, ±9.1 and ±14 mrad failed at
    every value.  Aligning the vehicle on the route therefore belongs to the placement work (the
    geometry decides where the body sits and which way it points), and this test keeps the seat from
    quietly growing a fifth unknown family in the meantime.
    """

    path = _case(tmp_path, "yaw_untouched", radius=1100.0, cant=0.107, speed_kmh=100.0,
                 duration_s=0.002)
    case = load_vehicle_case(path)
    dynamics = VehicleDynamics(case, contact_workers=1)
    topology = dynamics.topology
    yaw_rows = [topology.require(body.id, "yaw") for body in topology.bodies if "yaw" in body.dof]
    assert yaw_rows
    from velch.vehicle_solver import _static_vertical_equilibrium

    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    before = q[yaw_rows].copy()
    seated, _residual = _static_vertical_equilibrium(case, dynamics, q, v)
    assert np.array_equal(seated[yaw_rows], before)
