"""The 18号 turnout seats only when every axle is inside the station table.

Measured before the fix: at ``x_start = 30`` m the rear axles sit at 22.5 and 20.0 m while the table
starts at 30 m, so four wheels have no rail under them and the seat reports
``unbalanced branch - 4 of 8 wheels carry load``.  Moving the start to 45 m puts all eight wheels on
rail and the same code seats 8/8 at 0.97-1.03 times the even share.  Nothing about the physics
changed, so this is a case-versus-geometry test, not a tolerance test.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, SimulationFailure, _seat

pytestmark = pytest.mark.corpus

EVEN_SHARE_N = 59_662.0
LOW, HIGH = 0.625, 1.6


def _turnout_case(tmp_path, start_m: float):
    raw = json.loads((data_root.case_dir() / "case_diverging_R1100.json").read_text(encoding="utf-8"))
    raw["run"].update({"x_start_m": start_m, "duration_s": 0.01, "output_step_s": 0.01})
    raw.pop("initial_state", None)
    path = tmp_path / f"turnout_{start_m:g}.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return load_vehicle_case(path)


def _seat_and_load(case):
    dynamics = VehicleDynamics(case)
    q, velocity = np.zeros(dynamics.dimension), np.zeros(dynamics.dimension)
    seated, residual = _seat(case, dynamics, q, velocity)
    dynamics.placement_enabled = True
    dynamics.evaluate(0.0, seated, velocity)
    loads = [
        float(response.wheel_force_z_n)
        for group in dynamics.body_contacts.values()
        for response in group
    ]
    return residual, loads


def test_every_axle_inside_the_table_seats_all_eight_wheels(tmp_path):
    case = _turnout_case(tmp_path, 45.0)
    residual, loads = _seat_and_load(case)
    active = [load for load in loads if load > 0.0]
    assert residual < 1e-5
    assert len(active) == 8
    ratios = [load / EVEN_SHARE_N for load in active]
    assert min(ratios) >= LOW and max(ratios) <= HIGH


def test_a_rear_axle_outside_the_table_is_refused_not_flattened(tmp_path):
    case = _turnout_case(tmp_path, 30.0)
    with pytest.raises(SimulationFailure) as error:
        _seat_and_load(case)
    assert "unbalanced branch" in str(error.value)
