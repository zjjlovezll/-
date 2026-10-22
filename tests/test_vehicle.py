from dataclasses import replace
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, save_vehicle_result, simulate_vehicle


CASE = Path(__file__).resolve().parents[1] / "examples/vehicle_v2/case.json"


def test_vehicle_connector_mass_symmetry_and_internal_balance():
    case = load_vehicle_case(CASE)
    system = VehicleDynamics(case)
    assert system.dimension == 59
    assert len(system.connectors) == 30
    assert len(case.rails) == 12
    assert case.vehicle.axle_offsets_m == (10.0, 7.5, -7.5, -10.0)
    assert np.all(system.mass > 0)
    stiffness = sum((link.stiffness * np.outer(link.jacobian, link.jacobian)
                     for link in system.connectors), np.zeros((system.dimension, system.dimension)))
    damping = sum((link.damping * np.outer(link.jacobian, link.jacobian)
                   for link in system.connectors), np.zeros_like(stiffness))
    assert np.allclose(stiffness, stiffness.T)
    assert np.allclose(damping, damping.T)
    assert np.linalg.eigvalsh(stiffness).min() >= -1e-7
    assert np.linalg.eigvalsh(damping).min() >= -1e-7
    q = np.linspace(-1e-5, 1e-5, system.dimension)
    v = np.linspace(1e-4, -1e-4, system.dimension)
    internal = sum((link.force(q, v) for link in system.connectors), np.zeros(system.dimension))
    y_indices = [5 * i for i in range(4)] + [20, 25, 30]
    z_indices = [5 * i + 1 for i in range(4)] + [21, 26, 31]
    assert abs(sum(internal[y_indices])) < 1e-7
    assert abs(sum(internal[z_indices])) < 1e-7


def test_four_axle_turnout_run_and_vehicle_parameter_change(tmp_path):
    case = load_vehicle_case(CASE)
    base = simulate_vehicle(case)
    assert base.summary["result_status"] == "numerically_checked"
    assert base.summary["vertical_preload_max_residual_n"] < 0.1
    assert base.summary["active_output_samples"]["axle1_right_switch"] > 0
    assert base.summary["active_output_samples"]["axle2_right_switch"] == 0
    history, manifest = save_vehicle_result(case, base, tmp_path)
    assert history.is_file() and manifest.is_file()
    updated_wheelset = replace(case.vehicle.wheelset, mass_kg=case.vehicle.wheelset.mass_kg * 1.2)
    modified = replace(case, vehicle=replace(case.vehicle, wheelset=updated_wheelset),
                       run=replace(case.run, duration_s=0.001, output_step_s=0.0005))
    heavier = simulate_vehicle(modified)
    assert heavier.summary["vertical_preload_max_residual_n"] < 0.1
    assert not np.isclose(base.positions[0, 1], heavier.positions[0, 1], atol=1e-8)
