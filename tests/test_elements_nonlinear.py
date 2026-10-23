"""Nonlinear force elements: the two laws, and the Jacobian they owe the solver."""
from __future__ import annotations

import numpy as np
import pytest

from velch.elements import BlowoffDamperLaw, BumpStopLaw, PARAMETERS, build, parse
from velch.jacobian import frozen_geometry_error
from velch.topology import TopologyError, topology_of
from velch.vehicle import VehicleParameters, load_vehicle_case
from velch.vehicle_solver import Connector, VehicleDynamics
from velch.data_root import case_dir

CFG = VehicleParameters(
    carbody={"mass_kg": 32000.0, "roll_inertia_kg_m2": 1.0e5, "pitch_inertia_kg_m2": 1.7e6,
             "yaw_inertia_kg_m2": 1.6e6},
    bogie={"mass_kg": 3200.0, "roll_inertia_kg_m2": 2600.0, "pitch_inertia_kg_m2": 1700.0,
           "yaw_inertia_kg_m2": 3200.0},
    wheelset={"mass_kg": 1780.0, "roll_inertia_kg_m2": 949.0, "spin_inertia_kg_m2": 118.0,
              "yaw_inertia_kg_m2": 967.0},
    primary={"k_y_n_m": 9.8e5, "c_y_n_s_m": 0.0, "k_z_n_m": 1.176e6, "c_z_n_s_m": 1.0e4,
             "k_yaw_n_m": 1.96e6, "c_yaw_n_s_m": 0.0, "half_width_m": 1.0,
             "upper_anchor_height_m": -0.322, "lower_anchor_height_m": -0.585},
    secondary={"k_y_n_m": 1.6e5, "c_y_n_s_m": 0.0, "k_z_n_m": 2.4e5, "c_z_n_s_m": 2.0e4,
               "k_yaw_n_m": 8.85e6, "c_yaw_n_s_m": 2.45e6, "half_width_m": 1.23,
               "upper_anchor_height_m": -1.0, "lower_anchor_height_m": -1.4},
    bogie_half_spacing_m=8.75,
    wheelbase_m=2.5,
    wheel_center_height_m=0.43,
    nominal_wheel_radius_m=0.43,
    travel_speed_m_s=97.2222,
    gravity_m_s2=9.81,
    drive_torque_per_wheelset_nm=0.0,
)


def test_a_bump_stop_is_free_play_then_a_spring() -> None:
    law = BumpStopLaw(stiffness_n_m=1.0e6, gap_m=0.002)
    assert law.force(-0.001, 0.0) == 0.0
    assert law.stiffness(-0.001) == 0.0
    assert law.force(-0.004, 0.0) == pytest.approx(-2000.0)
    assert law.stiffness(-0.004) == pytest.approx(1.0e6)
    # The potential is the integral of the law, so energy and force cannot disagree.
    # The gap itself is a kink (one-sided derivative), so measure strictly inside each branch.
    for extension in (-0.001, -0.0025, -0.0035, -0.006):
        step = 1e-7
        slope = ((law.potential(extension + step) - law.potential(extension - step))
                 / (2.0 * step))
        assert slope == pytest.approx(law.force(extension, 0.0), rel=1e-6, abs=1e-6)


def test_a_blowoff_damper_has_two_slopes_and_the_valve_opens() -> None:
    law = BlowoffDamperLaw(low_speed_n_s_m=4.0e4, high_speed_n_s_m=5.0e3, blowoff_speed_m_s=0.05)
    assert law.force(0.0, 0.01) == pytest.approx(400.0)
    assert law.force(0.0, 0.05) == pytest.approx(2000.0)
    assert law.force(0.0, 0.20) == pytest.approx(2750.0)
    assert law.force(0.0, -0.20) == pytest.approx(-2750.0)
    assert law.damping(0.04) == pytest.approx(4.0e4)
    assert law.damping(0.20) == pytest.approx(5.0e3)
    # dF/dv must equal the reported damping on both sides of the knee.
    for rate in (0.02, 0.30):
        step = 1e-8
        slope = (law.force(0.0, rate + step) - law.force(0.0, rate - step)) / (2.0 * step)
        assert slope == pytest.approx(law.damping(rate), rel=1e-6)


def test_the_type_table_names_the_new_elements() -> None:
    assert "bump_stop" in PARAMETERS
    assert "damper_blowoff" in PARAMETERS
    assert PARAMETERS["bump_stop"]["stiffness"] == ("N/m", True)
    assert PARAMETERS["damper_blowoff"]["blowoff_speed"] == ("m/s", True)


def test_a_bump_stop_without_stiffness_is_refused_with_units() -> None:
    with pytest.raises(TopologyError, match=r"bump_stop.*'stiffness'.*N/m"):
        parse({"kind": "bump_stop", "name": "stop", "from": {"body": "a"}})


def test_a_blowoff_damper_needs_three_positive_numbers() -> None:
    base = {"kind": "damper_blowoff", "name": "d", "from": {"body": "a"},
            "low_speed_damping": 4e4, "high_speed_damping": 5e3, "blowoff_speed": 0.05}
    assert parse(base).parameters["blowoff_speed"] == pytest.approx(0.05)
    for key in ("low_speed_damping", "high_speed_damping", "blowoff_speed"):
        broken = dict(base)
        broken[key] = 0.0
        with pytest.raises(TopologyError, match=key):
            parse(broken)


def test_building_a_bump_stop_hands_back_a_law_not_a_stiffness() -> None:
    block = {
        "model": "v2-node",
        "pitch_sign": -1.0,
        "bodies": [
            {"id": "carbody", "kind": "carbody", "dof": ["y", "z"],
             "mass_kg": 1000.0, "inertia": {}},
            {"id": "bogie1", "kind": "bogie", "dof": ["y", "z"],
             "mass_kg": 500.0, "inertia": {}, "bogie": 1},
        ],
        "elements": [
            {"kind": "bump_stop", "name": "stop_z", "stiffness": 8.0e5, "gap_m": 0.001,
             "direction": [0, 0, 1],
             "from": {"body": "carbody", "point": [0.0, 0.0, 0.0]},
             "to": {"body": "bogie1", "point": [0.0, 0.0, 0.0]}},
        ],
    }
    topology = topology_of(block, CFG)
    link = topology.link_specs[0]
    assert isinstance(link.law, BumpStopLaw)
    assert link.law.gap_m == pytest.approx(0.001)
    assert link.stiffness == 0.0  # the slope lives in the law, not in the linear row


def _dynamics() -> VehicleDynamics:
    case = load_vehicle_case(case_dir() / "case_frog_N_strip05.json")
    return VehicleDynamics(case, contact_workers=1)


@pytest.mark.corpus
def test_the_analytic_jacobian_follows_a_nonlinear_row() -> None:
    """An engaged stop changes the block, and the assembled Jacobian must change with it."""

    dynamics = _dynamics()
    n = dynamics.dimension
    q = np.array(dynamics.case.initial_q, dtype=float)
    v = np.zeros(n)
    for index in range(dynamics.topology.body_dimension):
        q[index] = 0.0
    dynamics.evaluate(0.0, q, v)

    target = next(link for link in dynamics.connectors if link.name.startswith("secondary_b1_L_z"))
    extension = target.extension(q)
    law = BumpStopLaw(stiffness_n_m=6.0e6, gap_m=-(extension) - 1.0e-4)
    links = list(dynamics.connectors)
    position = links.index(target)
    links[position] = Connector(target.name, target.axis, 0.0, 0.0, target.rest,
                                target.jacobian, law)
    dynamics.connectors = tuple(links)

    assert law.stiffness(extension) == pytest.approx(6.0e6)  # the stop is engaged here
    error = frozen_geometry_error(dynamics, 0.0, q, v)
    assert error["dq_worst_column"] < 2.0e-4
    assert error["dv_worst_column"] < 2.0e-4

    # Disengaging it must remove that row's stiffness from the block.
    loose = Connector(target.name, target.axis, 0.0, 0.0, target.rest, target.jacobian,
                      BumpStopLaw(stiffness_n_m=6.0e6, gap_m=0.5))
    links[position] = loose
    dynamics.connectors = tuple(links)
    assert loose.stiffness_at(q) == 0.0
