"""The speed schedule is a value: constant pass-through, leg integration, and refusals."""

from __future__ import annotations

import math

import pytest

from velch.speed import Leg, SpeedSchedule, SpeedScheduleError


def test_a_constant_schedule_is_the_closed_form_the_solver_already_uses() -> None:
    schedule = SpeedSchedule.constant(97.2222, duration_s=1.2)
    assert schedule.is_constant
    assert schedule.constant_speed_m_s == pytest.approx(97.2222)
    for t in (0.0, 0.0173, 0.5, 1.2, 7.5):
        assert schedule.x_at(t, x_start_m=13.5) == 13.5 + 97.2222 * t
        assert schedule.v_at(t) == 97.2222


def test_a_constant_schedule_reports_its_length_from_the_requested_duration() -> None:
    schedule = SpeedSchedule.constant(20.0, duration_s=3.0)
    assert schedule.duration_s == pytest.approx(3.0)
    assert schedule.distance_m == pytest.approx(60.0)


def test_two_legs_integrate_exactly_where_the_closed_forms_meet() -> None:
    schedule = SpeedSchedule.from_legs([
        Leg(speed_m_s=20.0, duration_s=2.0),
        Leg(speed_m_s=40.0, duration_s=1.0),
    ])
    assert not schedule.is_constant
    assert schedule.duration_s == pytest.approx(3.0)
    assert schedule.distance_m == pytest.approx(80.0)
    assert schedule.x_at(0.0) == pytest.approx(0.0)
    assert schedule.x_at(1.0) == pytest.approx(20.0)
    assert schedule.x_at(2.0) == pytest.approx(40.0)
    assert schedule.x_at(2.5) == pytest.approx(60.0)
    assert schedule.x_at(3.0) == pytest.approx(80.0)
    # asking past the end holds the last speed rather than extrapolating a wrong one
    assert schedule.v_at(10.0) == 40.0


def test_a_distance_leg_is_a_duration_leg_in_disguise() -> None:
    schedule = SpeedSchedule.from_legs([
        Leg(speed_m_s=25.0, distance_m=100.0),
        Leg(speed_m_s=10.0, distance_m=20.0),
    ])
    assert schedule.duration_s == pytest.approx(4.0 + 2.0)
    assert schedule.x_at(4.0) == pytest.approx(100.0)
    assert schedule.x_at(6.0) == pytest.approx(120.0)
    assert schedule.min_speed_m_s == 10.0
    assert schedule.max_speed_m_s == 25.0


def test_x_at_is_linear_inside_every_leg_and_continuous_at_its_edges() -> None:
    """A midpoint sum across two speed steps is first order (dt * dv / 2 per edge), so it
    cannot check this to 1e-9; the property that can be checked exactly is that x_at is
    linear with the leg's own speed inside the leg."""
    schedule = SpeedSchedule.from_legs([
        Leg(speed_m_s=18.0, duration_s=0.75),
        Leg(speed_m_s=31.0, duration_s=0.5),
        Leg(speed_m_s=12.0, duration_s=0.25),
    ])
    starts = schedule.starts_s
    for index, leg in enumerate(schedule.legs):
        start = starts[index]
        end = starts[index + 1]
        base = schedule.x_at(start)
        for fraction in (0.0, 0.13, 0.5, 0.87, 1.0):
            moment = start + fraction * (end - start)
            assert schedule.x_at(moment) == pytest.approx(base + leg.speed_m_s * (moment - start), rel=1e-12)
    # the pieces add up to the reported distance
    assert schedule.x_at(schedule.duration_s) == pytest.approx(schedule.distance_m, rel=1e-12)
    assert schedule.distance_m == pytest.approx(18.0 * 0.75 + 31.0 * 0.5 + 12.0 * 0.25, rel=1e-12)


def test_a_schedule_with_one_speed_repeated_is_still_constant() -> None:
    schedule = SpeedSchedule.from_legs([
        Leg(speed_m_s=30.0, duration_s=1.0),
        Leg(speed_m_s=30.0, distance_m=60.0),
    ])
    assert schedule.is_constant
    assert schedule.constant_speed_m_s == 30.0
    assert schedule.x_at(2.5) == 75.0


def test_the_refusals_name_what_is_wrong() -> None:
    with pytest.raises(SpeedScheduleError, match="at least one leg"):
        SpeedSchedule(legs=())
    with pytest.raises(SpeedScheduleError, match="finite and positive"):
        Leg(speed_m_s=0.0, duration_s=1.0)
    with pytest.raises(SpeedScheduleError, match="exactly one of"):
        Leg(speed_m_s=1.0)
    with pytest.raises(SpeedScheduleError, match="exactly one of"):
        Leg(speed_m_s=1.0, duration_s=1.0, distance_m=2.0)
    with pytest.raises(SpeedScheduleError, match="duration must be finite and positive"):
        Leg(speed_m_s=1.0, duration_s=-1.0)
    with pytest.raises(SpeedScheduleError, match="not constant"):
        SpeedSchedule.from_legs([
            Leg(speed_m_s=1.0, duration_s=1.0),
            Leg(speed_m_s=2.0, duration_s=1.0),
        ]).constant_speed_m_s
    with pytest.raises(SpeedScheduleError, match="must not be negative"):
        SpeedSchedule.constant(1.0).v_at(-0.1)
    with pytest.raises(SpeedScheduleError, match="must be finite"):
        SpeedSchedule.constant(1.0).v_at(math.inf)


def test_the_description_states_the_speeds_and_not_an_average() -> None:
    schedule = SpeedSchedule.from_legs([
        Leg(speed_m_s=20.0, duration_s=1.0),
        Leg(speed_m_s=40.0, duration_s=1.0),
    ])
    text = schedule.describe()
    assert "2 legs" in text
    assert "20.000" in text and "40.000" in text
    assert "constant" in SpeedSchedule.constant(5.0).describe()

def test_a_constant_spec_names_its_unit() -> None:
    schedule = SpeedSchedule.from_spec({"constant": {"speed_kmh": 80.0}})
    assert schedule.is_constant
    assert schedule.constant_speed_m_s == pytest.approx(80.0 / 3.6)


def test_legs_can_mix_the_two_units_and_the_two_lengths() -> None:
    schedule = SpeedSchedule.from_spec({"legs": [
        {"speed_kmh": 72.0, "duration_s": 1.0},
        {"speed_m_s": 30.0, "distance_m": 60.0},
    ]})
    assert schedule.speeds[0] == pytest.approx(20.0)
    assert schedule.duration_s == pytest.approx(1.0 + 2.0)
    assert schedule.distance_m == pytest.approx(20.0 + 60.0)


def test_the_spec_refuses_an_ambiguous_or_unknown_shape() -> None:
    with pytest.raises(SpeedScheduleError, match="exactly one of 'constant' and 'legs'"):
        SpeedSchedule.from_spec({})
    with pytest.raises(SpeedScheduleError, match="exactly one of 'constant' and 'legs'"):
        SpeedSchedule.from_spec({"constant": {"speed_kmh": 1.0}, "legs": []})
    with pytest.raises(SpeedScheduleError, match="unknown speed_profile keys"):
        SpeedSchedule.from_spec({"constant": {"speed_kmh": 1.0}, "extra": 1})
    with pytest.raises(SpeedScheduleError, match="exactly one of 'speed_kmh' and 'speed_m_s'"):
        SpeedSchedule.from_spec({"constant": {"speed_kmh": 1.0, "speed_m_s": 1.0}})
    with pytest.raises(SpeedScheduleError, match="leg 0 has unknown keys"):
        SpeedSchedule.from_spec({"legs": [{"speed_kmh": 1.0, "bogus": 1}]})
