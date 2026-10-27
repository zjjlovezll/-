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
import pathlib

import pytest

import velch.vehicle_solver

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import (
    SimulationFailure,
    VehicleDynamics,
    _place_on_alignment,
    _static_vertical_equilibrium,
    _load_per_wheel,
    simulate_vehicle,
)

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
          speed_kmh: float, duration_s: float = 0.01,
          geometry: bool = False) -> pathlib.Path:
    raw = json.loads(_base_path().read_text(encoding="utf-8"))
    raw["run"].update({"x_start_m": 60.0, "duration_s": duration_s,
                       "output_step_s": duration_s})
    if radius is not None:
        raw["run"]["curve_radius_m"] = float(radius)
        raw["run"]["curve_cant_m"] = float(cant)
    if geometry:
        raw["run"]["curve_geometry"] = True
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


def test_a_contact_guard_inside_the_seat_rejects_the_step_instead_of_escaping(tmp_path):
    """The guard fires during the static search, and it must not escape from it.

    Measured: R = 1100 m, no cant, 100 km/h, ``curve_geometry = true``, slope guard tightened to
    0.20 — the least-squares search probes states that are fatal to integrate, and the guard fires
    ~149 times per seat.  Before the barrier it escaped as
    ``graph slope limit at axle1_left/left:main, x=70 m``, which described the probe rather than the
    model; now the step is rejected, the count is reported, and the seat reports the honest
    ``vertical preload equilibrium failed``.  The guard keeps its value for time stepping.
    """

    path = _case(tmp_path, "barrier", radius=1100.0, cant=0.0, speed_kmh=100.0, geometry=True)
    raw = json.loads(path.read_text(encoding="utf-8"))
    # 0.02 is far below any real flank slope, so the search trips it on purpose: the barrier
    # only has a job while the guard can fire at all.
    raw["run"]["maximum_abs_contact_slope"] = 0.02
    path.write_text(json.dumps(raw, indent=1, ensure_ascii=False), encoding="utf-8")

    dynamics = VehicleDynamics(load_vehicle_case(path), contact_workers=1)
    # The seat raises, so it is called directly: the point is the counter left behind.
    q = _place_on_alignment(dynamics.case, dynamics,
                            np.array(dynamics.case.initial_q, dtype=float))
    v = np.array(dynamics.case.initial_v, dtype=float)
    # Whether the seat converges or not, the guard must never escape as its own message: that was
    # the defect this test exists for.  Since the curve body force stopped being double-counted on
    # the geometry route, a no-cant curve now seats here, so convergence is an allowed outcome.
    try:
        _static_vertical_equilibrium(dynamics.case, dynamics, q, v)
    except SimulationFailure as error:
        assert "vertical preload equilibrium failed" in str(error)
    assert dynamics.seat_barrier_hits > 0, "the guard never fired, so this test proves nothing"


def test_a_geometric_curve_runs_and_passes_every_gate(tmp_path):
    """R = 1100 m with no cant at 100 km/h: the seat converges and the run is quotable.

    Three rounds got here.  The seat had to stop asking for a lateral equilibrium that cannot exist
    at zero speed (round 31), and the action-reaction gate had to stop counting m v^2/R on the route
    that places the vehicle instead of pushing it (round 32).  Before the second fix this case ran
    and failed exactly one gate by exactly the curve force.
    """

    path = _case(tmp_path, "unbalanced", radius=1100.0, cant=0.0, speed_kmh=100.0)
    result = simulate_vehicle(load_vehicle_case(path))
    gates = getattr(result, "gates", None) or {}
    if gates:
        assert all(gates.values()), {name: value for name, value in gates.items() if not value}


def _seat(dynamics: VehicleDynamics):
    """The state the solver starts from: placed, then seated vertically."""

    q = _place_on_alignment(dynamics.case, dynamics,
                            np.array(dynamics.case.initial_q, dtype=float))
    v = np.array(dynamics.case.initial_v, dtype=float)
    q, _ = _static_vertical_equilibrium(dynamics.case, dynamics, q, v)
    return q, v


def test_the_seat_puts_no_lateral_coordinate_among_its_unknowns():
    """The seat solves vertical coordinates only, even when the run has a curve.

    Round 31 measured why: at zero speed the creep forces that would balance a curve are exactly
    zero and a crown contact carries no lateral component, so lateral, yaw and roll rows have no
    solution.  Their presence made the system rank deficient -- cond 3.76e12, smallest singular
    value 2.7e-11, every seed stationary at 240 kN -- while the vertical coordinates alone
    converge to 1.07e-12 with eight patches at 65.47 um and 58.7..60.6 kN.
    """

    source = pathlib.Path(velch.vehicle_solver.__file__).read_text(encoding="utf-8")
    assert "axes = (" not in source
    assert "Lateral, yaw and roll stay *out* of the seat's unknowns" in source


def test_curve_geometry_places_the_vehicle_on_the_line_it_moves_the_track_onto(tmp_path):
    """The track and the vehicle must agree about where the curve is.

    ``curve_geometry`` moves the rails onto ``y(s) = s^2/(2R)``.  A vehicle that keeps ``y = yaw = 0``
    then stands beside them and the seat can only close that gap by riding the flange.  Placement
    gives every body the line's own offset and heading at its own mileage, so the wheelbase is
    rotated by ``footprint / R`` instead of being dragged there.
    """

    from velch.vehicle_solver import VehicleDynamics, _body_offset_m, _place_on_alignment

    # cant = 0: the level difference a rail cannot yet be tilted for is refused elsewhere, and
    # placement itself is about the curve's line, not about cant.
    path = _case(tmp_path, "placed", radius=1100.0, cant=0.0, speed_kmh=100.0,
                 duration_s=0.005, geometry=True)
    case = load_vehicle_case(path)
    dynamics = VehicleDynamics(case, contact_workers=1)
    topology = dynamics.topology
    q = np.asarray(case.initial_q, dtype=float)
    placed = _place_on_alignment(case, dynamics, q)
    assert not np.array_equal(placed, q)
    for body in topology.wheelsets():
        s = _body_offset_m(case, topology, body, placed)
        assert placed[topology.require(body.id, "y")] == pytest.approx(s * s / 2200.0, abs=1e-15)
        assert placed[topology.require(body.id, "yaw")] == pytest.approx(np.arctan(s / 1100.0),
                                                                         abs=1e-15)
    by_axle = sorted(topology.wheelsets(),
                     key=lambda body: _body_offset_m(case, topology, body, placed))
    front, rear = by_axle[0], by_axle[-1]
    s_front = _body_offset_m(case, topology, front, placed)
    s_rear = _body_offset_m(case, topology, rear, placed)
    assert s_front != s_rear
    spread = (float(placed[topology.require(rear.id, "yaw")])
              - float(placed[topology.require(front.id, "yaw")]))
    # Two headings add, they do not compose: atan(a) + atan(b) differs from atan(a + b) in the third
    # order, which is 5e-6 rad over this footprint and not a placement error.
    assert spread == pytest.approx(np.arctan((s_rear - s_front) / 1100.0), abs=2e-5)
    # A case without the geometry flag has no line to sit on, so placement must leave it alone.
    straight = load_vehicle_case(_case(tmp_path, "no_geometry", radius=1100.0, cant=0.107,
                                       speed_kmh=100.0, duration_s=0.005))
    straight_dynamics = VehicleDynamics(straight, contact_workers=1)
    untouched = _place_on_alignment(straight, straight_dynamics,
                                    np.asarray(straight.initial_q, dtype=float))
    assert np.array_equal(untouched, np.asarray(straight.initial_q, dtype=float))


@pytest.mark.xfail(strict=True, reason=(
    "the analytic geometry route is blocked inside the contact search: with curve_geometry the "
    "rails are rolled by the cant and the wheel envelope becomes non-monotonic at cant 0 and 0.107 "
    "(ValueError from contact.py:106), while 0.02 and 0.05 trip the slope guard.  Placement is in "
    "place, so this is the next blocker, not a placement error."))
def test_the_analytic_geometry_route_would_run_if_the_contact_search_allowed_it(tmp_path):
    path = _case(tmp_path, "geometry_run", radius=1100.0, cant=0.107, speed_kmh=100.0,
                 duration_s=0.005, geometry=True)
    result = simulate_vehicle(load_vehicle_case(path))
    assert result.summary["result_status"] == "numerically_checked"

@pytest.mark.corpus
def test_cant_on_the_geometry_route_is_refused_because_of_the_wheel_transform(tmp_path):
    """Rolling one of the two surfaces cannot publish cant, so the route now refuses it.

    Measured with the rail surface rolled: the contact lands on the rail shoulder, ``lever_y``
    -714.322 mm against a rail band of -785.4..-713.2 mm, because rotating a wheel by phi carries its
    tread contact point ``R sin(phi) = 30.8 mm`` inboard while the rail crown moves 5 mm at most.  A
    balanced curve needs the vehicle frame tilted with the track plane, which this route does not do,
    so the refusal names the measurement instead of publishing a shoulder contact as a tread one.
    The force route (``curve_geometry = false``) seats the same case.
    """

    from velch import data_root

    raw = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
    raw["run"].update({"curve_radius_m": 1100.0, "curve_cant_m": 0.107, "curve_geometry": True,
                       "duration_s": 0.01, "output_step_s": 0.01, "x_start_m": 60.0})
    raw.pop("initial_state", None)
    raw.pop("path", None)
    path = tmp_path / "cant_on_geometry.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")

    with pytest.raises(ValueError) as error:
        load_vehicle_case(path)
    message = str(error.value)
    assert "R sin(phi) = 30.8 mm" in message
    assert "vehicle frame tilted" in message


@pytest.mark.corpus
def test_a_350_metre_curve_at_its_eighty_limit_sits_within_the_band(tmp_path):
    """R = 350 m, no cant, 80 km/h: every wheel inside [0.5, 1.6] x the even share.

    This is the acceptance point the architecture review asked for, at the speed the diverging
    route is actually limited to rather than at 100 km/h.  The measured shares were
    57.3-75.6 kN against an even share of 59.66 kN, i.e. 0.96-1.27x, and the run is quotable
    (seven of seven gates, maximum penetration 74.9 um).
    """

    path = _case(tmp_path, "r350_80", radius=350.0, cant=0.0, speed_kmh=80.0, geometry=True)
    result = simulate_vehicle(load_vehicle_case(path))
    summary = getattr(result, "summary", None) or {}
    gates = summary.get("gates", {})
    assert gates and all(gates.values()), {name: value for name, value in gates.items() if not value}
    peaks = summary.get("peak_normal_force_n", {})
    even = 59.66e3
    shares = sorted(value / even for value in peaks.values())
    assert 0.5 <= shares[0] and shares[-1] <= 1.6, (shares[0], shares[-1])


@pytest.mark.corpus
def test_an_uncompensated_350_metre_curve_runs_but_transfers_load(tmp_path):
    """R = 350 m at 100 km/h has no cant it could carry, so the outer wheel really does overload.

    The balance cant for this radius and speed is 0.337 m, above both the model's 0.20 m
    plausibility guard and the largest cant in service, so the honest statement is not "it fails"
    but "it runs, and the load transfer is the physics": measured leading-outer 166.9 kN and
    trailing-outer 104.4 kN against an even share of 59.66 kN (2.80x and 1.75x), seven of seven
    gates true, maximum penetration 177.7 um.
    """

    path = _case(tmp_path, "r350_100", radius=350.0, cant=0.0, speed_kmh=100.0, geometry=True)
    result = simulate_vehicle(load_vehicle_case(path))
    summary = getattr(result, "summary", None) or {}
    gates = summary.get("gates", {})
    assert gates and all(gates.values()), {name: value for name, value in gates.items() if not value}
    peaks = summary.get("peak_normal_force_n", {})
    worst = max(peaks.values()) / 59.66e3
    assert worst > 2.0, worst


@pytest.mark.corpus
def test_the_force_route_carries_no_load_transfer_and_must_not_be_quoted_as_a_curve(tmp_path):
    """A curve pushed as a body force transfers almost nothing: measured 1.0039 x on R = 350 m.

    With the lateral force applied to every body but the wheels still inside the clearance band,
    the rail never supplies a reaction, so the vertical loads stay even and the run still reports
    seven of seven gates -- the action-reaction gate counts the applied force by construction.
    Ten milliseconds is far too short for the flange to be reached (2.2 m/s^2 gives 0.11 mm).
    The geometry route, which places the vehicle on the arc, gives 2.80 x on the same case; that
    is the route a curve result may be quoted from.
    """

    force_route = _case(tmp_path, "r350_force", radius=350.0, cant=0.0, speed_kmh=100.0)
    geometry = _case(tmp_path, "r350_geom", radius=350.0, cant=0.0, speed_kmh=100.0, geometry=True)

    force_summary = getattr(simulate_vehicle(load_vehicle_case(force_route)), "summary", None) or {}
    geometry_summary = getattr(simulate_vehicle(load_vehicle_case(geometry)), "summary", None) or {}

    even = 59.66e3
    force_worst = max(force_summary["peak_normal_force_n"].values()) / even
    geometry_worst = max(geometry_summary["peak_normal_force_n"].values()) / even
    assert force_worst < 1.05, force_worst
    assert geometry_worst > 2.0, geometry_worst
