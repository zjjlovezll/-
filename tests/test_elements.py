"""The force-element library: types, parameters, and what each type actually connects."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from velch import elements, topology
from velch.vehicle import VehicleParameters

VEHICLES = Path(__file__).resolve().parent.parent / "vehicles"
CFG = VehicleParameters(**json.loads(
    (VEHICLES / "CRH380A_M.json").read_text(encoding="utf-8"))["vehicle"])


def _block(*raw: dict) -> dict:
    return {"bodies": [
        {"id": "a", "kind": "carbody", "dof": ["y", "z", "roll"], "mass_kg": 1000.0,
         "inertia": {"roll": 10.0, "pitch": 10.0, "yaw": 10.0}},
        {"id": "b", "kind": "carbody", "dof": ["y", "z"], "mass_kg": 1000.0,
         "inertia": {"roll": 10.0, "pitch": 10.0, "yaw": 10.0}},
    ], "elements": list(raw)}


def _spec(**kwargs) -> elements.ElementSpec:
    return elements.parse(kwargs)


def test_the_catalogue_names_units_for_every_parameter():
    kinds = {entry["kind"] for entry in elements.catalogue()}
    assert {"spring", "damper", "spring_damper", "bushing"} <= kinds
    for entry in elements.catalogue():
        for parameter in entry["parameters"]:
            assert parameter["unit"], f"{entry['kind']}.{parameter['name']} has no unit"


def test_a_spring_only_carries_stiffness():
    top = topology.topology_of(_block({"kind": "spring", "name": "s", "stiffness": 1000.0,
                                       "direction": [0.0, 0.0, 1.0],
                                       "from": {"body": "a"}, "to": {"body": "b"}}), CFG)
    (link,) = top.link_specs
    assert link.stiffness == pytest.approx(1000.0)
    assert link.damping == pytest.approx(0.0)


def test_a_damper_may_have_no_stiffness_at_all():
    top = topology.topology_of(_block({"kind": "damper", "name": "c", "damping": 40000.0,
                                       "direction": [0.0, 1.0, 0.0],
                                       "from": {"body": "a"}, "to": {"body": "b"}}), CFG)
    (link,) = top.link_specs
    assert link.stiffness == pytest.approx(0.0)
    assert link.damping == pytest.approx(40000.0)


def test_a_spring_damper_is_one_link_with_both():
    top = topology.topology_of(_block({"kind": "spring_damper", "name": "sd",
                                       "stiffness": 160000.0, "damping": 20000.0,
                                       "direction": [0.0, 0.0, 1.0],
                                       "from": {"body": "a"}, "to": {"body": "b"}}), CFG)
    (link,) = top.link_specs
    assert (link.stiffness, link.damping) == (pytest.approx(160000.0), pytest.approx(20000.0))


def test_a_bushing_with_cross_stiffness_becomes_principal_links():
    block = _block({"kind": "bushing", "name": "b", "stiffness": 5000.0,
                    "cross_stiffness": {"y-z": 1000.0},
                    "direction": [0.0, 0.0, 1.0],
                    "from": {"body": "a"}, "to": {"body": "b"}})
    top = topology.topology_of(block, CFG)
    # Neither body carries x, so the x principal direction is skipped and the y/z block is
    # what remains: eigenvalues 4000 and 6000 of the [[5000, 1000], [1000, 5000]] minor.
    assert len(top.link_specs) == 2
    stiffnesses = sorted(link.stiffness for link in top.link_specs)
    assert stiffnesses == pytest.approx([4000.0, 6000.0], rel=1e-6)
    # The eigen-decomposition preserves the trace of the part it could represent.
    assert sum(stiffnesses) == pytest.approx(10000.0, rel=1e-6)


def test_a_bushing_that_is_not_positive_definite_is_refused():
    block = _block({"kind": "bushing", "name": "b", "stiffness": 5000.0,
                    "cross_stiffness": {"y-z": 9000.0},
                    "direction": [0.0, 1.0, 0.0],
                    "from": {"body": "a"}, "to": {"body": "b"}})
    with pytest.raises(topology.TopologyError, match="positive semi-definite"):
        topology.topology_of(block, CFG)


def test_a_missing_required_parameter_names_the_element_and_the_unit():
    with pytest.raises(topology.TopologyError, match=r"'b' \(spring_damper\).*'damping'.*N·s/m"):
        topology.topology_of(_block({"kind": "spring_damper", "name": "b", "stiffness": 1.0,
                                     "direction": [0.0, 0.0, 1.0],
                                     "from": {"body": "a"}, "to": {"body": "b"}}), CFG)


def test_a_negative_parameter_is_refused_with_its_unit():
    with pytest.raises(topology.TopologyError, match="non-negative"):
        topology.topology_of(_block({"kind": "spring", "name": "s", "stiffness": -1.0,
                                     "direction": [0.0, 0.0, 1.0],
                                     "from": {"body": "a"}, "to": {"body": "b"}}), CFG)


def test_an_unknown_kind_lists_what_is_known():
    with pytest.raises(topology.TopologyError, match="known kinds"):
        topology.topology_of(_block({"kind": "air spring", "name": "x", "stiffness": 1.0,
                                     "direction": [0.0, 0.0, 1.0],
                                     "from": {"body": "a"}, "to": {"body": "b"}}), CFG)


def test_duplicate_element_names_are_refused():
    with pytest.raises(topology.TopologyError, match="duplicate element name"):
        topology.topology_of(_block(
            {"kind": "spring", "name": "s", "stiffness": 1.0,
             "direction": [0.0, 0.0, 1.0], "from": {"body": "a"}, "to": {"body": "b"}},
            {"kind": "spring", "name": "s", "stiffness": 2.0,
             "direction": [0.0, 1.0, 0.0], "from": {"body": "a"}, "to": {"body": "b"}},
        ), CFG)


def test_inherited_values_are_resolved_before_the_library_sees_them():
    top = topology.topology_of(_block({"kind": "spring_damper", "name": "sd",
                                       "stiffness": "$vehicle.primary.k_z_n_m",
                                       "damping": "$vehicle.primary.c_z_n_s_m",
                                       "direction": [0.0, 0.0, 1.0],
                                       "from": {"body": "a"}, "to": {"body": "b"}}), CFG)
    (link,) = top.link_specs
    assert link.stiffness == pytest.approx(CFG.primary["k_z_n_m"])
    assert link.damping == pytest.approx(CFG.primary["c_z_n_s_m"])
