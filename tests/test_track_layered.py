"""Tests for the general layered track kernel.

The layered kernel is the software answer to the user's stage-3 stack
(钢轨、扣件、轨枕、板下胶垫、轨道板): the number of layers is a case input, not
code. These tests pin the contract:

* dimension is 2*(1+L) per rail and the DOF order is rail, layer 1, layer 2, ...
* the static force path is a series spring chain,
* the ground reaction equals the load carried,
* the potential is the elastic energy of the same chain.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from velch.model import LinearSupport, TrackLayer
from velch.track_models import TrackKernel


def make_rail(rail_id: str = "axle1_right", k_pad: float = 25.0e6) -> SimpleNamespace:
    return SimpleNamespace(
        id=rail_id,
        template_id="tpl",
        mass_y_kg=100.0,
        mass_z_kg=100.0,
        support=LinearSupport(k_y_n_m=k_pad, c_y_n_s_m=0.0, k_z_n_m=k_pad, c_z_n_s_m=0.0),
    )


def layers_two() -> tuple[TrackLayer, ...]:
    return (
        TrackLayer(mass_y_kg=79.0, mass_z_kg=79.0,
                   k_y_n_m=6.0e6, c_y_n_s_m=0.0, k_z_n_m=12.0e6, c_z_n_s_m=0.0),
        TrackLayer(mass_y_kg=300.0, mass_z_kg=300.0,
                   k_y_n_m=25.0e6, c_y_n_s_m=0.0, k_z_n_m=50.0e6, c_z_n_s_m=0.0),
    )


def test_dimension_and_state_names_follow_the_layer_count() -> None:
    rail = make_rail()
    kernel = TrackKernel("layered", [rail], layers=layers_two())
    assert kernel.dimension == 2 * 3
    assert kernel.state_names == [
        "axle1_right_rail_y_m", "axle1_right_rail_z_m",
        "axle1_right_layer1_y_m", "axle1_right_layer1_z_m",
        "axle1_right_layer2_y_m", "axle1_right_layer2_z_m",
    ]


def test_layered_requires_a_layer() -> None:
    with pytest.raises(ValueError):
        TrackKernel("layered", [make_rail()], layers=())


def test_static_chain_is_series_springs() -> None:
    rail = make_rail(k_pad=25.0e6)
    layers = layers_two()
    kernel = TrackKernel("layered", [rail], layers=layers)
    load = 60.0e3
    # Force balance at each node of an elastic series chain:
    #   F = k_pad (q_r - q_1) = k_1 (q_1 - q_2) = k_2 q_2
    q = np.zeros(35 + kernel.dimension)
    q2 = load / layers[1].k_z_n_m
    q1 = q2 + load / layers[0].k_z_n_m
    qr = q1 + load / rail.support.k_z_n_m
    q[35 + 1] = qr
    q[35 + 3] = q1
    q[35 + 5] = q2
    internal = kernel.internal_force(q, np.zeros_like(q))
    assert internal[1] == pytest.approx(-load, rel=1e-12)
    assert internal[3] == pytest.approx(0.0, abs=1e-6)
    assert internal[5] == pytest.approx(0.0, abs=1e-6)


def test_ground_reaction_and_potential_match_the_load() -> None:
    rail = make_rail(k_pad=25.0e6)
    layers = layers_two()
    kernel = TrackKernel("layered", [rail], layers=layers)
    load = 60.0e3
    q = np.zeros(35 + kernel.dimension)
    q2 = load / layers[1].k_z_n_m
    q1 = q2 + load / layers[0].k_z_n_m
    qr = q1 + load / rail.support.k_z_n_m
    q[35 + 1], q[35 + 3], q[35 + 5] = qr, q1, q2
    _, vertical = kernel.support_reaction(q, np.zeros_like(q), [(0.0, load)])
    assert vertical == pytest.approx(load, rel=1e-12)
    # Elastic energy of a series chain under one load = 0.5 * F * total deflection.
    assert kernel.potential_j(q) == pytest.approx(0.5 * load * qr, rel=1e-12)
