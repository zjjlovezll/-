"""The node table must restate the frozen connectors exactly, and say so in a test."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from velch import topology as topology_module
from velch.vehicle import VehicleParameters
from velch.vehicle_db import VehicleModel, load as load_model, validate

VEHICLES = Path(__file__).resolve().parent.parent / "vehicles"


def test_the_six_dof_model_carries_the_mined_elements():
    model = load_model("CRH380A_M_6dof")
    names = {element["name"] for element in model.raw["topology"]["elements"]}
    assert {"traction_rod_front", "anti_roll_front", "lateral_damper_front"} <= names
    assert "mined_from" in model.raw, "a six-DOF model must say where the extra elements came from"


def test_a_node_model_must_declare_a_consistent_state_dimension():
    raw = json.loads((VEHICLES / "CRH380A_M_node.json").read_text(encoding="utf-8"))
    raw["layout"]["state_dimension"] = 35
    problems = validate(VehicleModel(path=VEHICLES / "CRH380A_M_node.json", raw=raw))
    assert any("state_dimension" in problem for problem in problems)


def test_an_element_that_connects_nothing_is_refused():
    cfg = VehicleParameters(**json.loads(
        (VEHICLES / "CRH380A_M.json").read_text(encoding="utf-8"))["vehicle"])
    # Two bodies with no overlapping coordinate: a y-only axial link between x-only bodies.
    block = {
        "bodies": [
            {"id": "a", "kind": "carbody", "dof": ["x"], "mass_kg": 1.0,
             "inertia": {"roll": 1.0, "pitch": 1.0, "yaw": 1.0}},
            {"id": "b", "kind": "carbody", "dof": ["x"], "mass_kg": 1.0,
             "inertia": {"roll": 1.0, "pitch": 1.0, "yaw": 1.0}},
        ],
        "elements": [{"kind": "axial", "name": "dead", "stiffness": 1.0,
                      "direction": [0.0, 0.0, 1.0],
                      "from": {"body": "a"}, "to": {"body": "b"}}],
    }
    with pytest.raises(topology_module.TopologyError):
        topology_module.topology_of(block, cfg)
