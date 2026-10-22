"""Is the frog-window residual smooth enough to invert?

The cached-grid experiment moved the peak from 170.9 to 1447.7 kN by shifting the
search grid half a step, which is either (a) a broken grid or (b) proof that the
forward map is bistable there. This separates the two: perturb one physical parameter
by +-0.5 %, which changes no discretisation at all, and see whether the answer moves
smoothly or jumps.

If +-0.5 % moves the peak by a fraction of a percent, the response is smooth and the
earlier jump was a grid defect. If it jumps by hundreds of kN, every inversion run
over this window is suspect and the window must be changed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

import sys

BASE = Path(__file__).resolve().parent
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "case_Z_local_rail.json"
TAG = SOURCE.stem
STEPS = (0.995, 1.000, 1.005)


def run(scale: float) -> dict:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    for template in raw["rail_templates"]:
        template["support"]["k_z_n_m"] *= scale
    raw["case_id"] = f"bist_{TAG}_{scale:g}"
    path = BASE / f"case_bist_{TAG}_{scale:g}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    case = load_vehicle_case(path)
    result = simulate_vehicle(case)
    force = np.array([entry["axle1_right"].normal_force_n for entry in result.contacts])
    height = np.asarray(result.positions[:, 1], dtype=float)
    return {
        "scale": scale,
        "status": result.summary.get("result_status"),
        "peak_kN": float(force.max()) / 1e3,
        "min_kN": float(force.min()) / 1e3,
        "lost": int(np.count_nonzero(force <= 0.0)),
        "samples": int(force.size),
        "span_mm": float(1e3 * (height.max() - height.min())),
    }


def main() -> int:
    rows = [run(scale) for scale in STEPS]
    print(f"{'scale':>8}{'peak kN':>11}{'min kN':>10}{'lost':>7}{'span mm':>11}")
    for row in rows:
        print(f"{row['scale']:>8.3f}{row['peak_kN']:>11.2f}{row['min_kN']:>10.3f}"
              f"{row['lost']:>7}{row['span_mm']:>11.3f}")
    reference = rows[1]
    for row in rows:
        if row is reference:
            continue
        delta = row["peak_kN"] - reference["peak_kN"]
        print(f"  scale {row['scale']:.3f}: peak {delta:+.2f} kN "
              f"({100.0 * delta / reference['peak_kN']:+.2f} %)")
    (BASE / f"bistability_scan_{TAG}.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
