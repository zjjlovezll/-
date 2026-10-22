"""Print the run block of a few derived cases (no PowerShell JSON parsing)."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
for name in ("case_imp_bdf_analytic.json", "case_imp_bdf_sparse.json",
             "case_full12_cap05.json", "case_frog_long_bdf_analytic.json"):
    path = BASE / name
    if not path.exists():
        print(f"{name}: missing")
        continue
    raw = json.loads(path.read_text(encoding="utf-8"))
    run = raw.get("run", {})
    print(f"{name}: x_start={run.get('x_start_m')} duration={run.get('duration_s')} "
          f"method={run.get('method')} jac={run.get('jacobian')} "
          f"max_step={run.get('max_solver_step_s')} rtol={run.get('rtol')}")
