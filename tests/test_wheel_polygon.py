"""The wheel polygon, and the fact that it reaches the wheel profile.

A polygon is a radial error that repeats once per revolution, so it is described in the
wheelset's own rotating frame: ``order`` lobes, ``depth_m`` amplitude, one phase.  The
solver evaluates it at the current spin angle and drops the wheel profile by that amount,
because the profile's ``z`` is "height below the wheel centre" (radius ``R = -z``).
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from velch.vehicle import WheelPolygon, load_vehicle_case

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "vehicle_v2" / "case.json"


def _absolute(node):
    """Profile paths resolve against the case's own directory, so a copy must be absolute."""

    if isinstance(node, dict):
        for key, value in node.items():
            if key == "file" and isinstance(value, str) and not Path(value).is_absolute():
                node[key] = str((EXAMPLE.parent / value).resolve())
            else:
                _absolute(value)
    elif isinstance(node, list):
        for item in node:
            _absolute(item)
    return node


def _case(tmp_path: Path, polygon: dict | None, duration_s: float = 0.004) -> Path:
    raw = _absolute(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    raw = copy.deepcopy(raw)
    raw["run"]["duration_s"] = duration_s
    raw["run"]["output_step_s"] = duration_s / 4.0
    raw.pop("wheel_polygon", None)
    if polygon is not None:
        raw["wheel_polygon"] = polygon
    path = tmp_path / "case_polygon.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_a_polygon_is_geometry_not_a_force():
    polygon = WheelPolygon(order=20, depth_m=20.0e-6)
    radius = 0.43
    # A 20th-order polygon on a 430 mm wheel is a 135 mm wave, and at 350 km/h that is 720 Hz.
    assert polygon.wavelength_m(radius) == pytest.approx(2.0 * math.pi * radius / 20.0)
    assert polygon.frequency_hz(350.0 / 3.6, radius) == pytest.approx(
        20.0 * (350.0 / 3.6) / (2.0 * math.pi * radius)
    )


def test_the_radius_offset_is_the_cosine_of_the_spin_angle():
    polygon = WheelPolygon(order=4, depth_m=30.0e-6)
    assert polygon.radius_offset_m(0.0) == pytest.approx(30.0e-6)
    assert polygon.radius_offset_m(math.pi / (2.0 * 4.0)) == pytest.approx(0.0, abs=1e-15)
    assert polygon.radius_offset_m(math.pi / 4.0) == pytest.approx(-30.0e-6)
    # It averages to zero over one revolution, which is why a static solve can ignore it.
    angles = np.linspace(0.0, 2.0 * math.pi, 721)[:-1]
    assert np.mean([polygon.radius_offset_m(a) for a in angles]) == pytest.approx(0.0, abs=1e-12)


def test_a_polygon_needs_an_order_and_a_positive_depth():
    with pytest.raises(ValueError):
        WheelPolygon(order=0, depth_m=1e-6)
    with pytest.raises(ValueError):
        WheelPolygon(order=10, depth_m=0.0)
    with pytest.raises(ValueError):
        WheelPolygon(order=10, depth_m=-1e-6)


def test_the_case_reads_the_block_and_a_plain_case_has_none(tmp_path):
    plain = load_vehicle_case(_case(tmp_path, None))
    assert plain.wheel_polygon is None

    other = tmp_path / "with"
    other.mkdir()
    loaded = load_vehicle_case(_case(other, {"order": 10, "depth_m": 3.0e-5}))
    assert loaded.wheel_polygon is not None
    assert loaded.wheel_polygon.order == 10
    assert loaded.wheel_polygon.depth_m == pytest.approx(3.0e-5)


def test_the_out_of_round_lowers_the_contact_point_and_leaves_the_depth(tmp_path):
    """A smaller radius moves the contact point down in the wheel frame, not the penetration.

    The static solve is free to sink the wheelset by the same amount, so the penetration it
    lands on is unchanged; what a dynamic run sees is the contact point riding up and down.
    """

    from velch.vehicle_solver import VehicleDynamics, _static_vertical_equilibrium

    plain = VehicleDynamics(load_vehicle_case(_case(tmp_path, None)))
    other = tmp_path / "with"
    other.mkdir()
    shaped = VehicleDynamics(
        load_vehicle_case(_case(other, {"order": 10, "depth_m": 3.0e-5, "phase_rad": 0.0}))
    )

    assert plain._out_of_round_shift(plain.case.rails[0], np.zeros(plain.dimension)) == 0.0
    assert shaped._out_of_round_shift(
        shaped.case.rails[0], np.zeros(shaped.dimension)
    ) == pytest.approx(3.0e-5)

    levers = {}
    depths = {}
    for label, dynamics in (("plain", plain), ("shaped", shaped)):
        q = np.array(dynamics.case.initial_q, float)
        v = np.zeros_like(q)
        q, _ = _static_vertical_equilibrium(dynamics.case, dynamics, q, v)
        _force, contacts = dynamics.evaluate(0.0, q, v)
        responses = contacts.values() if hasattr(contacts, "values") else contacts
        response = next(item for item in responses if getattr(item, "geometry", None) is not None)
        geometry = response.geometry
        levers[label] = geometry.lever_z_m
        depths[label] = geometry.penetration_m

    assert levers["shaped"] - levers["plain"] == pytest.approx(-3.0e-5, abs=2e-6)
    assert depths["shaped"] == pytest.approx(depths["plain"], abs=2e-6)
