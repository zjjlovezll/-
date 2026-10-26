"""A whole state vector must survive a change of layout, and a truncated one must be refused.

The night this was fixed, O010 had been blamed on the node-table layouts for two rounds.  The
real cause was cheaper: ``remap_state`` carries only the *body* block, and a caller that hands it a
whole vector gets the track block cut off.  Every rail row is then short by exactly one contact
patch (59 662 N at the static seat), which reads as a physical imbalance -- a car standing on one
side -- instead of as a truncated vector.
"""
from __future__ import annotations

import pytest

from velch.topology import TopologyError, legacy_topology, migrate_initial_state, remap_state


def _legacy_and_node():
    from velch.topology import node_topology
    from velch.vehicle import vehicle_parameters
    from velch.vehicle_db import load

    legacy = legacy_topology(vehicle_parameters(load("CRH380A_M").block))
    node_raw = load("CRH380A_M_node").raw
    node = node_topology(node_raw["topology"], vehicle_parameters(node_raw["vehicle"]))
    return legacy, node


def test_remap_state_refuses_a_whole_state_vector():
    legacy, node = _legacy_and_node()
    whole = [0.0] * (legacy.body_dimension + 24)
    with pytest.raises(TopologyError) as caught:
        remap_state(whole, legacy, node)
    message = str(caught.value)
    assert "migrate_initial_state" in message
    assert str(legacy.body_dimension) in message


def test_migrate_carries_the_track_block_verbatim():
    legacy, node = _legacy_and_node()
    whole = [float(i) for i in range(legacy.body_dimension + 24)]
    moved = migrate_initial_state(whole, legacy, node, tracks=24)
    assert len(moved) == node.body_dimension + 24
    assert moved[node.body_dimension:] == [
        float(i) for i in range(legacy.body_dimension, legacy.body_dimension + 24)]


def test_body_coordinates_land_by_name_and_new_axes_start_at_zero():
    legacy, node = _legacy_and_node()
    whole = [0.0] * (legacy.body_dimension + 24)
    whole[legacy.require("carbody", "z")] = -0.001234
    whole[legacy.require("wheelset1", "y")] = 3.5e-05
    moved = migrate_initial_state(whole, legacy, node, tracks=24)
    assert moved[node.require("carbody", "z")] == pytest.approx(-0.001234)
    assert moved[node.require("wheelset1", "y")] == pytest.approx(3.5e-05)
    carbody = next(body for body in node.bodies if body.id == "carbody")
    if "x" in carbody.dof:
        assert moved[node.require("carbody", "x")] == 0.0


def test_modal_coordinates_are_appended_as_zero():
    legacy, node = _legacy_and_node()
    whole = [0.5] * (legacy.body_dimension + 24)
    moved = migrate_initial_state(whole, legacy, node, tracks=24, modal_size=124)
    assert len(moved) == node.body_dimension + 24 + 124
    assert moved[-124:] == [0.0] * 124


def test_a_vector_that_fits_neither_layout_is_refused():
    legacy, node = _legacy_and_node()
    with pytest.raises(TopologyError) as caught:
        migrate_initial_state([0.0] * 7, legacy, node, tracks=24)
    assert "7 values" in str(caught.value)
