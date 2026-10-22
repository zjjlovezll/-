"""Does the hoisted rail grid reproduce the adaptive grid now that the key is fixed?

Runs the same case twice -- adaptive grid (grid_step_m = 0) and hoisted uniform grid
(grid_step_m = 0.25 mm) -- and reports peak force, lost samples, wheel travel and the
contact cost measured inside the run. A pass means the two agree to the last digit that
matters and the hoisted path is faster.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

BASE = Path(__file__).resolve().parent


def run(source: Path, step: float) -> dict:
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw.setdefault("contact", {})["grid_step_m"] = step
    raw["case_id"] = f"{source.stem}_grid{step:g}"
    path = BASE / f"case_grid_{source.stem}_{step:g}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    started = time.perf_counter()
    result = simulate_vehicle(load_vehicle_case(path))
    wall = time.perf_counter() - started
    force = np.array([entry["axle1_right"].normal_force_n for entry in result.contacts])
    height = np.asarray(result.positions[:, 1], dtype=float)
    return {
        "step": step,
        "wall_s": wall,
        "status": result.summary.get("result_status"),
        "peak_kN": float(force.max()) / 1e3,
        "min_kN": float(force.min()) / 1e3,
        "lost": int(np.count_nonzero(force <= 0.0)),
        "span_mm": float(1e3 * (height.max() - height.min())),
        "nfev": result.summary.get("solver", {}).get("nfev"),
    }


def main() -> int:
    source = Path(sys.argv[1])
    rows = [run(source, 0.0), run(source, 2.5e-4)]
    print(f"{'step m':>10}{'wall s':>9}{'peak kN':>10}{'min kN':>9}{'lost':>6}"
          f"{'span mm':>10}{'nfev':>9}")
    for row in rows:
        print(f"{row['step']:>10.4g}{row['wall_s']:>9.1f}{row['peak_kN']:>10.2f}"
              f"{row['min_kN']:>9.3f}{row['lost']:>6}{row['span_mm']:>10.3f}"
              f"{row['nfev']:>9}")
    base, cand = rows
    print(f"  peak delta {cand['peak_kN'] - base['peak_kN']:+.3f} kN "
          f"({100.0 * (cand['peak_kN'] / base['peak_kN'] - 1.0):+.3f} %)")
    print(f"  wall delta {100.0 * (cand['wall_s'] / base['wall_s'] - 1.0):+.1f} %")
    (BASE / f"grid_cache_fix_{source.stem}.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
