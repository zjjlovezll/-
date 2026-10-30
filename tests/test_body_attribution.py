"""M0: a rail body's force adds up to the wheel force, and a buried blade carries nothing.

``evaluate`` merges the bodies of one track side into one response so the caller sees the force the
wheel feels.  The merge is a sum by construction, and the reported geometry is the *deepest* body --
which is why "which body carries the load" is invisible in the return value and has to be read
through ``body_contacts`` / ``BODY_CONTACT_HOOK``.

Two failures this pins, both of which have produced confident wrong numbers in this repository:

* the two records of one evaluation (``_body_cache`` for the Jacobian, ``contacts`` for the wheel)
  drifting apart -- which is how "the blade is loaded at 50.627 m" could be reported while the blade
  was still 14.94 mm below the running surface;
* a body claiming a contact it cannot have.  The blade is buried 14.94 mm at its tip and the static
  penetration is 65.4661 um -- 228x smaller -- so inside the first metres of the blade region its
  normal force must be exactly zero.

Only frames on the turnout geometry can show either, hence the corpus marker: the straight baseline
carries three right-side bodies (stock 76 stations / blade 161 / frog 65).
"""

from __future__ import annotations

import pathlib

import numpy as np
import pytest

import velch.vehicle_solver as vs
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _static_vertical_equilibrium

pytestmark = pytest.mark.corpus

CASE = pathlib.Path("vehicles/turnouts/CN60-1100-1_18/cases/straight.json")
STATIC_PENETRATION_M = 65.4661e-6
BLADE_START_M = 50.578
# The blade reaches the running surface about 7.4 m into its own table, so a second live body is only
# possible from there on: at 60 m the two crowns are 14 um apart, far inside the 65.47 um static
# penetration, while at 51.98 m the blade is still 7.2 mm down and carries nothing.
FLUSH_STATION_M = 60.0
BLADE_LOWERING_MM = 14.94


@pytest.fixture(scope="module")
def seated():
    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    speed = float(case.vehicle.travel_speed_m_s)
    velocity = np.zeros(dynamics.dimension)
    for body in dynamics.topology.bodies:
        spin = dynamics.topology.index(body.id, "spin")
        if spin is not None:
            velocity[spin] = speed / 0.43
    state, residual = _static_vertical_equilibrium(
        case, dynamics, np.array(case.initial_q, dtype=float), velocity)
    yield case, dynamics, np.asarray(state, dtype=float), velocity, speed, residual
    dynamics.close()


def _time_for_front_axle(case, speed: float, station_m: float) -> float:
    """Time at which the first axle's contact patch reaches ``station_m``.

    The patch station is ``x_at(t) + axle_offsets_m[axle]`` (``VehicleDynamics.station_m``), so the
    offset comes from the case instead of from a copied constant.
    """
    return float((station_m - case.run.x_start_m - case.vehicle.axle_offsets_m[0]) / speed)


def _capture_hook(dynamics, t_s: float, state: np.ndarray, velocity: np.ndarray):
    captured: list[tuple[str, tuple[tuple[str, float], ...]]] = []

    def hook(_t: float, rail_id: str, entries) -> None:
        captured.append((rail_id, tuple(entries)))

    previous = vs.BODY_CONTACT_HOOK
    vs.BODY_CONTACT_HOOK = hook
    try:
        _force, contacts = dynamics.evaluate(t_s, state, velocity)
    finally:
        vs.BODY_CONTACT_HOOK = previous
    return captured, contacts


def test_the_bodies_of_one_side_add_up_to_the_force_the_wheel_feels(seated) -> None:
    case, dynamics, state, velocity, speed, residual = seated
    assert abs(residual) < 1.0e-6

    # Where the blade has risen to the running surface: a right-hand side really does have two bodies
    # alive at once there.  At the blade tip only the stock rail can touch (see the buried-blade test).
    t_s = _time_for_front_axle(case, speed, FLUSH_STATION_M)
    _force, contacts = dynamics.evaluate(t_s, state, velocity)

    multi_body = 0
    for rail in case.rails:
        bodies = dynamics.body_contacts[rail.id]
        if sum(1 for item in bodies if item.active) > 1:
            multi_body += 1
        total = sum(item.normal_force_n for item in bodies if item.active)
        merged = contacts[rail.id]
        expected = float(merged.normal_force_n) if merged.active else 0.0
        assert abs(total - expected) <= 1.0e-9 * max(abs(expected), 1.0), (
            f"{rail.id}: bodies sum to {total!r} N but the wheel is integrated with {expected!r} N")

    assert multi_body >= 1, "no side had two live bodies, so the sum test proved nothing"


def test_the_hook_reports_one_entry_per_live_body_and_matches_the_rail_total(seated) -> None:
    case, dynamics, state, velocity, speed, _residual = seated
    t_s = _time_for_front_axle(case, speed, FLUSH_STATION_M)
    captured, contacts = _capture_hook(dynamics, t_s, state, velocity)

    assert captured, "the hook never fired"
    by_rail = dict(captured)
    assert any(len(entries) >= 2 for entries in by_rail.values()), (
        "no rail reported two bodies, so this test could not see a per-body split")
    for rail in case.rails:
        entries = by_rail[rail.id]
        known = {body.id for body in rail.contact_bodies}
        assert {body_id for body_id, _force in entries} <= known, (
            f"{rail.id}: the hook named a body the rail does not carry")
        total = sum(force for _body_id, force in entries)
        merged = contacts[rail.id]
        expected = float(merged.normal_force_n) if merged.active else 0.0
        assert abs(total - expected) <= 1.0e-9 * max(abs(expected), 1.0), (
            f"{rail.id}: the hook reports {total!r} N, the wheel gets {expected!r} N")


def test_a_blade_that_is_still_buried_carries_no_load(seated) -> None:
    case, dynamics, state, velocity, speed, _residual = seated
    # 1.4 m into the blade region the design lowering is still millimetres (14.94 mm at the tip over
    # a 6.4 m ramp), so nothing about the blade can be touching the tread.
    t_s = _time_for_front_axle(case, speed, BLADE_START_M + 1.4)
    captured, _contacts = _capture_hook(dynamics, t_s, state, velocity)

    blades = [(rail_id, force) for rail_id, entries in captured
              for body_id, force in entries if body_id == "blade"]
    assert blades, "no rail reported a blade body at all"
    for rail_id, force_n in blades:
        assert force_n <= 1.0, (
            f"{rail_id}: the blade carries {force_n!r} N while it is still millimetres down")

    # And no body anywhere may claim more penetration than the static seat, which is the same
    # statement read off the geometry instead of the force.
    for rail in case.rails:
        for entry in dynamics.body_contacts[rail.id]:
            if entry.geometry is not None:
                assert entry.geometry.penetration_m <= STATIC_PENETRATION_M * 1.01, (
                    f"{rail.id}: a body claims {entry.geometry.penetration_m!r} m of penetration, "
                    "deeper than the static seat by any margin")


def _crown_m(body, station_m: float) -> float:
    """Highest z of that body's section at that station, in the model frame (z positive up)."""
    sample = body.series.sample(station_m, 1.0)
    return float(np.max(np.asarray(sample.profile.z_m, dtype=float)))


def test_the_drawn_blade_starts_14_94_mm_below_the_stock_and_rises_to_flush(seated) -> None:
    """The design lowering is section geometry, so it must never be added as a z offset again.

    An earlier builder injected ``z_offset_m = +lowering`` on top of sections that already carried it.
    That raised the tip by 14.94 mm and left the blade **3.3 mm above** the stock around 52 m, giving
    the blade body 1 079 365 N at 51.978 m -- a load it cannot have.  The three readings below are the
    whole story: below by the design amount at the tip, flush at the far end, never above in between.
    """
    case, _dynamics, _state, _velocity, _speed, _residual = seated
    rail = next(item for item in case.rails if item.id.endswith("_right"))
    bodies = {body.id: body for body in rail.contact_bodies}
    stock, blade = bodies["stock"], bodies["blade"]

    tip_gap_mm = (_crown_m(blade, BLADE_START_M) - _crown_m(stock, BLADE_START_M)) * 1e3
    assert tip_gap_mm == pytest.approx(-BLADE_LOWERING_MM, abs=0.15), (
        f"at the blade tip the drawn sections sit {tip_gap_mm:+.3f} mm against the stock, "
        f"the drawing says {-BLADE_LOWERING_MM:+.2f} mm")

    flush_gap_mm = (_crown_m(blade, 64.9) - _crown_m(stock, 64.9)) * 1e3
    assert abs(flush_gap_mm) <= 0.2, (
        f"at 64.9 m the blade should be flush with the stock, measured {flush_gap_mm:+.3f} mm")

    worst_mm, worst_at = -1e9, 0.0
    for station in np.arange(BLADE_START_M, min(blade.series.highest_m, 100.0), 0.05):
        gap_mm = (_crown_m(blade, float(station)) - _crown_m(stock, float(station))) * 1e3
        if gap_mm > worst_mm:
            worst_mm, worst_at = gap_mm, float(station)
    assert worst_mm <= 0.2, (
        f"the blade stands {worst_mm:+.3f} mm above the stock at {worst_at:.2f} m; "
        "a lowered blade can never be the higher of the two inside its ramp")


def test_the_body_ids_name_the_entries_they_belong_to(seated) -> None:
    """The run archive writes one column per body, so the names must line up with the responses.

    Only the bodies active at that station report -- at 50.0 m the blade's table has not started, so
    the right rail returns one entry and the rail's declared three are not the answer.  That is why
    the ids travel beside the responses instead of being reconstructed from the case.
    """
    case, dynamics, state, velocity, speed, _residual = seated
    declared = {rail.id: {body.id for body in rail.contact_bodies} for rail in case.rails}

    for station in (case.run.x_start_m + case.vehicle.axle_offsets_m[0], FLUSH_STATION_M):
        t_s = _time_for_front_axle(case, speed, station)
        dynamics.evaluate(t_s, state, velocity)
        ids = dynamics.body_ids
        responses = dynamics.body_contacts
        assert set(ids) == set(responses), "the id map and the response map name different rails"
        for rail_id, names in ids.items():
            assert len(names) == len(responses[rail_id]), (
                f"{rail_id}: {len(names)} names for {len(responses[rail_id])} responses")
            assert set(names) <= declared[rail_id], (
                f"{rail_id}: ids {sorted(names)} are not all bodies the rail carries")

    dynamics.evaluate(_time_for_front_axle(case, speed, FLUSH_STATION_M), state, velocity)
    live = [(rail_id, names) for rail_id, names in dynamics.body_ids.items()
            if len(names) > 1
            and sum(1 for item in dynamics.body_contacts[rail_id] if item.active) > 1]
    assert live, "no station reported two live bodies, so the column naming proved nothing"
