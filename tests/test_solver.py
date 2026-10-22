from pathlib import Path

import numpy as np
import pytest

from velch.model import RunSettings, load_case
from velch.solver import Dynamics, save_result, simulate


CASE = Path(__file__).resolve().parents[1] / "examples/synthetic_transfer/case.json"


def test_reaction_balance_and_unsupported_method():
    case = load_case(CASE)
    dynamics = Dynamics(case)
    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    q[1] = 0.4595  # create a small contact compression
    force, contacts = dynamics.evaluate(0.03, q, v)
    expected_z = -case.wheelset.mass_kg * case.wheelset.gravity_m_s2
    expected_z -= case.suspension.support.k_z_n_m * (q[1] - case.suspension.z_reference_m)
    expected_z -= sum(rail.support.k_z_n_m * q[4 + 2 * i + 1]
                      for i, rail in enumerate(case.rails))
    assert np.isclose(force[1] + sum(force[5::2]), expected_z, atol=1e-8)
    assert any(contact.active for contact in contacts.values())
    with pytest.raises(ValueError, match="supported methods"):
        RunSettings("Newmark", 0.0, 0.1, 0.01, 0.001, 1e-6, 1e-8, 0.01, 1.0)


def test_synthetic_turnout_transfer_outputs_quality_record(tmp_path):
    case = load_case(CASE)
    result = simulate(case)
    assert result.summary["result_status"] == "numerically_checked"
    assert result.summary["physics_validation_status"].startswith("unvalidated")
    assert result.summary["active_output_samples"]["right_stock"] > 0
    assert result.summary["active_output_samples"]["right_switch"] > 0
    assert np.all(np.isfinite(result.positions))
    history, manifest = save_result(case, result, tmp_path)
    assert history.is_file() and manifest.is_file()
    data = np.genfromtxt(history, delimiter=",", names=True)
    for rail in case.rails:
        assert np.min(data[f"{rail.id}_penetration_m"]) >= 0.0
