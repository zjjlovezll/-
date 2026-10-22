"""Compare prescribed maximum steps on the synthetic case; save evidence."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from velch.model import load_case
from velch.solver import simulate

ROOT = Path(__file__).resolve().parents[1]
case = load_case(ROOT / "examples/synthetic_transfer/case.json")
coarse = simulate(case)
fine_case = replace(case, run=replace(case.run, max_solver_step_s=case.run.max_solver_step_s / 2))
fine = simulate(fine_case)
normal_differences = {}
for rail in case.rails:
    a = coarse.summary["peak_normal_force_n"][rail.id]
    b = fine.summary["peak_normal_force_n"][rail.id]
    normal_differences[rail.id] = abs(a - b) / max(1.0, abs(b))
report = {
    "case_id": case.case_id,
    "coarse_max_step_s": case.run.max_solver_step_s,
    "fine_max_step_s": fine_case.run.max_solver_step_s,
    "final_wheel_z_difference_m": abs(float(coarse.positions[-1, 1] - fine.positions[-1, 1])),
    "peak_normal_relative_difference": normal_differences,
    "coarse_nfev": coarse.solver_evaluations,
    "fine_nfev": fine.solver_evaluations,
    "criterion": "final wheel z difference <= 1e-5 m; each sampled peak normal relative difference <= 0.02",
}
report["passed"] = (report["final_wheel_z_difference_m"] <= 1e-5
                    and all(value <= 0.02 for value in normal_differences.values()))
output = ROOT / "diagnostics/step_convergence.json"
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
if not report["passed"]:
    raise SystemExit(2)
