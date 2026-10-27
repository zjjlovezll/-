"""The route's offset transports the wheel; it must not be spent as lateral creep (B040).

A vehicle that follows the design line has ``dq[y]/dt = 0`` *against the rail*: the rail and the wheel
move together, so the material sliding velocity across the contact is zero.  ``v * dy/ds`` is the rate
at which the curve carries a point of the reference frame through Cartesian space -- a property of the
coordinate change, not of the contact.

Getting this wrong is not a subtle offset.  Measured on the 18-turnout diverging route (R = 1100 m,
80 km/h, seated, every state velocity except spin exactly zero): with the rate fed in as creep,
``slip_lateral`` came out +0.5737 / +0.5232 / +0.2205 / +0.1700 m/s and ``sum(Fy)`` = -36 939 N
against the +21 842 N the curve actually needs; with the rate removed, ``slip_lateral`` is exactly
0.0000 and ``sum(Fy)`` = +292 N.  The full record from the fixed code trips the slope guard 2.29 m
after the start, i.e. before it ever reaches the corrugation patch.

These tests pin the two halves: the helper still describes the frame transport honestly, and the
solver does not spend it on the contact.
"""

from __future__ import annotations

import pathlib

import numpy as np
import pytest

import velch.vehicle_solver as vehicle_solver
from velch.paths import PathTrack

RADIUS_M = 1100.75
SPEED_M_S = 80.0 / 3.6


def _arc_path() -> PathTrack:
    """A 200 m reference line with y = s^2 / (2R), sampled the way a case supplies one."""

    station_m = np.arange(0.0, 200.0 + 1e-9, 0.5)
    lateral_m = station_m**2 / (2.0 * RADIUS_M)
    return PathTrack(tuple(float(s) for s in station_m), tuple(float(y) for y in lateral_m))


def test_the_helper_reports_the_frame_transport_and_not_a_sliding_velocity() -> None:
    """`lateral_velocity_m_s` is v * dy/ds: it is the curve moving, and it grows with mileage."""

    path = _arc_path()
    near = path.lateral_velocity_m_s(20.0, SPEED_M_S)
    far = path.lateral_velocity_m_s(180.0, SPEED_M_S)
    # The table is piecewise linear, so the helper must be exactly the chord slope times the speed.
    assert near == SPEED_M_S * path.slope_at(20.0)
    assert far == SPEED_M_S * path.slope_at(180.0)
    assert far > 8.0 * near
    # The claim in one line: this number is ~0.61 m/s at 80 km/h, which is 50x the creep that
    # saturates the friction law -- so spending it on the contact changes the answer completely.
    on_curve = path.lateral_velocity_m_s(30.0, SPEED_M_S)
    assert 0.55 < on_curve < 0.65
    # Within 1 % of the analytic v * s / R; the gap is the 0.5 m chord (its midpoint sits 0.25 m
    # further along, so the chord slope reads 0.83 % high there).
    assert on_curve / (SPEED_M_S * 30.0 / RADIUS_M) == pytest.approx(1.0, rel=1e-2)


def test_the_contact_is_not_given_a_lateral_velocity_carried_by_the_route() -> None:
    """Shape guard, because the physics of this one is a single call site.

    It is deliberately a source assertion: the defect was one `+ lateral_rate` on a keyword, it is
    invisible in every straight case (dy/ds = 0), and no cheap end-to-end test can distinguish it from
    a tolerance change.  The measurement that motivated it is in the module docstring.
    """

    source = pathlib.Path(vehicle_solver.__file__).read_text(encoding="utf-8")
    assert 'wheel_v_y_m_s=float(v[axes["y"]]),' in source
    assert 'lateral_rate' not in source
    assert "lateral_extra = path.at(x)" in source
