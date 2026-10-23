"""The node table against the frozen layout: element rows, inheritance, and state size.

These read case files, so they need the corpus; the pure checks live in ``test_topology.py``.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from velch.data_root import case_dir
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics

pytestmark = pytest.mark.corpus


def _case(step: str):
    return VehicleDynamics(load_vehicle_case(case_dir() / step), contact_workers=1)


def _keyed(jacobian, topology) -> dict[tuple[str, str], float]:
    names: list[tuple[str, str]] = []
    for body in topology.bodies:
        for dof in body.dof:
            names.append((body.id, dof))
    dense = np.asarray(jacobian).ravel()[: len(names)]
    return {names[i]: float(v) for i, v in enumerate(dense) if abs(v) > 1e-12}


def test_the_legacy_shortcut_reproduces_the_historical_layout():
    dynamics = _case("case_frog_N_strip05.json")
    assert dynamics.topology.body_dimension == 35
    assert dynamics.dimension == 35
    assert [body.id for body in dynamics.topology.bodies] == [
        "wheelset1", "wheelset2", "wheelset3", "wheelset4", "bogie1", "bogie2", "carbody"]
    assert len(dynamics.connectors) == 30


def test_the_node_table_restates_every_frozen_connector_exactly():
    legacy = _case("case_frog_N_strip05.json")
    node = _case("case_node_equiv.json")
    left = {connector.name: connector for connector in legacy.connectors}
    right = {connector.name: connector for connector in node.connectors}
    assert set(left) == set(right), "the node table must carry the same connectors"
    for name in left:
        a = _keyed(left[name].jacobian, legacy.topology)
        b = _keyed(right[name].jacobian, node.topology)
        for key in set(a) | set(b):
            assert a.get(key, 0.0) == pytest.approx(b.get(key, 0.0), abs=1e-9), (name, key)


def test_a_case_inherits_its_topology_from_the_vehicle_reference():
    case = load_vehicle_case(case_dir() / "case_node_equiv.json")
    assert case.topology is not None
    assert case.topology["model"] == "v2-node"
