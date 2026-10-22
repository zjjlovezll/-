"""Measure how integrator settings move Velch's cost on the real turnout section.

Runs the CRH380A_M turnout case over a 0.05 s window that starts inside the
switch (x_start = 60 m) and compares wall time, RHS evaluations, and the
resulting contact-force history against a baseline configuration.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

BASE = Path("validation/crh380a_m")
SOURCE = BASE / "case_B_turnout.json"

CONFIGS = (
    ("baseline DOP853 h<=1e-4", {"method": "DOP853", "max_solver_step_s": 1e-4, "rtol": 1e-6, "atol": 1e-8}),
    ("DOP853 h<=5e-4", {"method": "DOP853", "max_solver_step_s": 5e-4, "rtol": 1e-6, "atol": 1e-8}),
    ("DOP853 h<=1e-4 rtol1e-5 atol1e-7", {"method": "DOP853", "max_solver_step_s": 1e-4, "rtol": 1e-5, "atol": 1e-7}),
    ("Radau h<=1e-4", {"method": "Radau", "max_solver_step_s": 1e-4, "rtol": 1e-6, "atol": 1e-8}),
)

DURATION_S = 0.05
X_START_M = 60.0


def build_case(index: int, overrides: dict) -> Path:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    raw["case_id"] = f"crh380a_m_bench_{index}"
    raw["run"]["x_start_m"] = X_START_M
    raw["run"]["duration_s"] = DURATION_S
    raw["run"].update(overrides)
    path = BASE / f"case_bench_{index}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def normal_forces(result) -> dict[str, np.ndarray]:
    labels = sorted(result.contacts[0])
    return {
        label: np.array([frame[label].normal_force_n for frame in result.contacts])
        for label in labels
    }


def main() -> None:
    rows = []
    forces: dict[str, dict[str, np.ndarray]] = {}
    for index, (label, overrides) in enumerate(CONFIGS):
        path = build_case(index, overrides)
        case = load_vehicle_case(path)
        started = time.perf_counter()
        try:
            result = simulate_vehicle(case)
            elapsed = time.perf_counter() - started
            forces[label] = normal_forces(result)
            rows.append({
                "config": label,
                "overrides": overrides,
                "wall_s": round(elapsed, 2),
                "status": result.summary["result_status"],
                "gates_failed": [k for k, v in result.summary["gates"].items() if not v],
                "nfev": result.summary["solver"]["nfev"],
                "n_points": int(result.times_s.size),
                "peak_normal_force_n": round(max(result.summary["peak_normal_force_n"].values()), 1),
                "max_penetration_mm": round(1000 * float(result.summary["max_penetration_m"]), 4),
            })
        except Exception as exc:  # noqa: BLE001 - report, do not mask
            rows.append({
                "config": label,
                "overrides": overrides,
                "wall_s": round(time.perf_counter() - started, 2),
                "status": f"{type(exc).__name__}: {exc}",
                "gates_failed": None,
                "nfev": None,
                "n_points": None,
                "peak_normal_force_n": None,
                "max_penetration_mm": None,
            })
        print(f"[{index + 1}/{len(CONFIGS)}] {label}: {rows[-1]['wall_s']} s  {rows[-1]['status']}", flush=True)

    baseline_label = CONFIGS[0][0]
    print()
    header = f"{'config':34s} {'wall_s':>8s} {'nfev':>8s} {'peak_N':>10s} {'pen_mm':>8s}  status"
    print(header)
    for row in rows:
        print(f"{row['config']:34s} {row['wall_s']:8.2f} {str(row['nfev'] or '-'):>8s} "
              f"{str(row['peak_normal_force_n'] or '-'):>10s} {str(row['max_penetration_mm'] or '-'):>8s}  "
              f"{row['status']}")

    if baseline_label in forces:
        print()
        print("max |delta normal force| vs baseline, worst rail:")
        reference = forces[baseline_label]
        for label, series in forces.items():
            if label == baseline_label:
                continue
            worst = max(float(np.max(np.abs(series[k] - reference[k]))) for k in reference)
            row = next(r for r in rows if r["config"] == label)
            print(f"  {label:34s} {worst:12.3f} N   wall ratio {row['wall_s'] / rows[0]['wall_s']:.2f}x")

    (BASE / "bench_settings.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
