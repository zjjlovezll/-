"""Check conservative fixed-profile limit of the reduced-order contact model."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from velch.model import LinearSupport, load_case
from velch.solver import simulate

ROOT = Path(__file__).resolve().parents[1]
original = load_case(ROOT / "examples/synthetic_transfer/case.json")


def no_damping(support: LinearSupport) -> LinearSupport:
    return replace(support, c_y_n_s_m=0.0, c_z_n_s_m=0.0)


case = replace(
    original,
    wheelset=replace(original.wheelset, travel_speed_m_s=0.0),
    suspension=replace(original.suspension, support=no_damping(original.suspension.support),
                       c_roll_nm_s_rad=0.0),
    rails=tuple(replace(rail, support=no_damping(rail.support)) for rail in original.rails),
    contact=replace(original.contact, normal_damping_n_s_m_1p5=0.0,
                    friction_coefficient=0.0),
    initial_v=tuple(0.0 for _ in original.initial_v),
)
result = simulate(case)
start = result.summary["initial_mechanical_energy_j"]
change = result.summary["energy_change_j"]
report = {"case": "fixed_station_zero_damping_zero_friction", "initial_energy_j": start,
          "energy_change_j": change, "relative_change": abs(change) / abs(start),
          "criterion": "relative change < 1e-3",
          "passed": abs(change) / abs(start) < 1e-3}
(ROOT / "diagnostics/static_energy_probe.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
if not report["passed"]:
    raise SystemExit(2)
