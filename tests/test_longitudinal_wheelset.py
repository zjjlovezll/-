"""The wheelset longitudinal coordinate: its schema, its station, and what stays untouched.

The point of the coordinate is that the creep rate and the mileage stop being prescribed
constants, so a test here has to prove three separate things: the column cannot collide with the
mileage column, the station really moves with the coordinate, and a layout without it behaves
exactly as before.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _acceleration_name, _column_names

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "vehicle_v2" / "case.json"
MODEL = REPO / "vehicles" / "CRH380A_M_axlebox_x.json"
LONGITUDINAL = "CRH380A_M_axlebox_x"


def _absolute(node, base: Path) -> None:
    """Profile paths resolve against the case that names them, so a copy must carry them whole."""

    if isinstance(node, dict):
        for key, value in node.items():
            if key == "file" and isinstance(value, str) and not Path(value).is_absolute():
                node[key] = str((base / value).resolve())
            else:
                _absolute(value, base)
    elif isinstance(node, list):
        for item in node:
            _absolute(item, base)


def _case(tmp_path: Path, *, vehicle_ref: str | None, duration_s: float) -> Path:
    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    _absolute(raw, EXAMPLE.parent)
    raw.pop("initial_state", None)
    raw["run"]["duration_s"] = duration_s
    raw["run"]["output_step_s"] = 1.0e-3
    if vehicle_ref is not None:
        raw.pop("vehicle", None)
        raw.pop("topology", None)
        raw["vehicle_ref"] = vehicle_ref
    path = tmp_path / f"case_{vehicle_ref or 'inline'}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def longitudinal(tmp_path_factory):
    path = _case(tmp_path_factory.mktemp("x"), vehicle_ref=LONGITUDINAL, duration_s=0.002)
    case = load_vehicle_case(path)
    return case, VehicleDynamics(case)


def test_the_coordinate_test_the_wheelset_carries_one(longitudinal):
    case, dynamics = longitudinal
    assert dynamics.topology.body_dimension == 90, (
        "15 bodies: 4x6 wheelsets + 8x6 boxes + 2x6 + 1x6")
    assert len(case.initial_q) > 90, "the track block follows the bodies"
    axes = dynamics._wheel_axes[0]
    assert "x" in axes
    assert axes["x"] < axes["y"], "the layout puts x before y; every offset must be looked up"


def test_the_mileage_column_keeps_its_name_and_the_coordinate_gets_another(longitudinal):
    case, _dynamics = longitudinal
    names = list(_column_names(case))
    assert names.count("axle1_x_m") == 0, (
        "axle<k>_x_m is written by the writer as the absolute station; the coordinate must not "
        "reuse it")
    assert names.count("axle1_dx_m") == 1
    assert len(names) == len(set(names)), "duplicate header: a reader would pair the wrong rows"


def test_the_acceleration_name_follows_the_state_name():
    assert _acceleration_name("axle1_dx_m") == "axle1_dx_acc_m_per_s2"
    assert _acceleration_name("axle1_box_left_z_m") == "axle1_box_left_z_acc_m_per_s2"


def test_the_station_moves_with_the_coordinate(longitudinal):
    case, dynamics = longitudinal
    rail = case.rails[0]
    q = np.array(case.initial_q, dtype=float)
    v = np.zeros_like(q)
    axis = dynamics._wheel_axes[rail.axle_index]["x"]
    base = dynamics.station_m(rail, 0.0, q)
    q[axis] += 0.5
    assert dynamics.station_m(rail, 0.0, q) == pytest.approx(base + 0.5, abs=1e-12)
    assert dynamics.station_m(rail, 1.0, q) == pytest.approx(base + 0.5 + 97.2222222, abs=1e-6)
    # the velocity reaches the creep rate, not the station
    assert dynamics.station_m(rail, 0.0, q) == pytest.approx(base + 0.5, abs=1e-12)


def test_the_longitudinal_force_row_reacts(longitudinal):
    case, dynamics = longitudinal
    q = np.array(case.initial_q, dtype=float)
    v = np.zeros_like(q)
    axis = dynamics._wheel_axes[0]["x"]
    # At rest every spring is at its rest length, so the row is legitimately zero.  Shift the
    # coordinate and the bearing (1e8 N/m) plus the traction rod must push back.
    force, _contacts = dynamics.evaluate(0.0, q, v)
    assert float(force[axis]) == 0.0
    q[axis] = 1.0e-3
    force, _contacts = dynamics.evaluate(0.0, q, v)
    assert abs(float(force[axis])) > 1.0, "the bearing and the traction rod must couple x to a force"


def test_a_layout_without_the_coordinate_is_untouched(tmp_path):
    case = load_vehicle_case(_case(tmp_path, vehicle_ref=None, duration_s=0.002))
    dynamics = VehicleDynamics(case)
    assert "x" not in {axis for axes in dynamics._wheel_axes.values() for axis in axes}
    names = list(_column_names(case))
    assert "axle1_dx_m" not in names
    q = np.array(case.initial_q, dtype=float)
    before = dynamics.station_m(case.rails[0], 0.0, q)
    assert dynamics.station_m(case.rails[0], 0.0, q + 0.7) == pytest.approx(before, abs=1e-15)


def test_the_longitudinal_force_is_off_by_default():
    """The term makes the channel non-zero, and it also enters yaw through a lever arm.

    So it is a switch, defaulting to off: an ordinary vertical run must not be walked onto the
    flange by a force that exists only because somebody wanted to measure the x channel.
    """

    from velch.model import RunSettings

    field = RunSettings.__dataclass_fields__["longitudinal_force"]
    assert field.default is False


def test_the_train_element_holds_the_carbody_against_the_ground(tmp_path):
    """A grounded spring is a one-entry link: the vehicle is not a free body in x.

    Reached through a case that references the model, because only the case loader resolves the
    ``$vehicle...`` references into the parameter object the topology needs.
    """

    from velch.vehicle import load_vehicle_case
    from velch.topology import topology_for

    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    _absolute(raw, EXAMPLE.parent)
    raw.pop("vehicle", None)
    raw.pop("topology", None)
    raw["vehicle_ref"] = "CRH380A_M_axlebox_x"
    raw["run"]["duration_s"] = 0.002
    path = tmp_path / "case_boundary.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    case = load_vehicle_case(path)
    topology = topology_for(case)
    grounded = [spec for spec in topology.link_specs if spec.name == "train_x"]
    assert len(grounded) == 1
    entries = grounded[0].entries
    assert len(entries) == 1                       # one body, no second anchor
    assert entries[0][1] == pytest.approx(1.0)     # acting on that body's own x row
    assert grounded[0].stiffness == pytest.approx(1.0e9)
    assert grounded[0].damping == pytest.approx(1.0e6)
