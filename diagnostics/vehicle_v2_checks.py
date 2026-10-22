"""Numerical convergence and conservative-limit probes for the v2 vehicle."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

ROOT = Path(__file__).resolve().parents[1]
case = load_vehicle_case(ROOT / "examples/vehicle_v2/case.json")
coarse = simulate_vehicle(case)
fine_case = replace(case, run=replace(case.run, max_solver_step_s=case.run.max_solver_step_s / 2))
fine = simulate_vehicle(fine_case)
peak_errors = {}
for rail in case.rails:
    first = coarse.summary["peak_normal_force_n"][rail.id]
    second = fine.summary["peak_normal_force_n"][rail.id]
    peak_errors[rail.id] = abs(first - second) / max(1.0, abs(second))
convergence = {
    "coarse_max_step_s": case.run.max_solver_step_s,
    "fine_max_step_s": fine_case.run.max_solver_step_s,
    "final_carbody_z_difference_m": abs(float(coarse.positions[-1, 31] - fine.positions[-1, 31])),
    "maximum_peak_normal_relative_difference": max(peak_errors.values()),
    "peak_normal_relative_difference": peak_errors,
    "criterion": "carbody z <= 1e-5 m and all sampled normal peaks <= 2% relative",
}
convergence["passed"] = (convergence["final_carbody_z_difference_m"] <= 1e-5 and
                         convergence["maximum_peak_normal_relative_difference"] <= 0.02)


def no_damping(stage):
    return replace(stage, c_y_n_s_m=0.0, c_z_n_s_m=0.0, c_yaw_nm_s_rad=0.0)


vehicle = replace(case.vehicle, travel_speed_m_s=0.0,
                  primary=no_damping(case.vehicle.primary),
                  secondary=no_damping(case.vehicle.secondary))
rails = tuple(replace(rail, support=replace(rail.support, c_y_n_s_m=0.0,
                                            c_z_n_s_m=0.0)) for rail in case.rails)
conservative = replace(case, vehicle=vehicle, rails=rails,
                       contact=replace(case.contact, normal_damping_n_s_m_1p5=0.0,
                                       friction_coefficient=0.0),
                       initial_v=tuple(0.0 for _ in case.initial_v),
                       equilibrate_vertical=False,
                       run=replace(case.run, duration_s=0.005))
limit = simulate_vehicle(conservative)
initial_energy = limit.summary["initial_mechanical_energy_j"]
relative_change = abs(limit.summary["energy_change_j"]) / max(1.0, abs(initial_energy))
energy = {"initial_energy_j": initial_energy,
          "energy_change_j": limit.summary["energy_change_j"],
          "relative_change": relative_change,
          "criterion": "fixed position, zero damping/friction/drive torque: relative mechanical-energy change < 1e-3",
          "passed": relative_change < 1e-3}
report = {"case_id": case.case_id, "step_convergence": convergence,
          "conservative_limit": energy,
          "passed": convergence["passed"] and energy["passed"]}
target = ROOT / "diagnostics/vehicle_v2_checks.json"
target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
if not report["passed"]:
    raise SystemExit(2)
