"""Is the 399 kN at x = 56.80 m created by the contact damping?

The damped full run peaks in the switch panel, not at the frog, at a sample whose
penetration is only 170 um. Elastic Hertz alone gives 250 kN there, so the extra must be
the damping term c sqrt(delta) v. This sweeps c over the switch window and also reports the
pure elastic share, to separate the two.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_frog_strip_soft.json"
OUT = BASE / "out_switch_damp"

LEVELS = (1.0e6, 5.0e6, 1.0e7, 3.0e7)


def run(level: float) -> dict[str, float]:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    raw["case_id"] = f"switch_damp_{level:.0e}"
    raw["contact"]["normal_damping_n_s_m_1p5"] = level
    raw["run"]["x_start_m"] = 42.5
    raw["run"]["duration_s"] = 0.05
    path = BASE / f"case_{raw['case_id']}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

    case = load_vehicle_case(path)
    result = simulate_vehicle(case)
    out = OUT / raw["case_id"]
    save_vehicle_result(case, result, out)
    with (out / "history.csv").open(encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
    data = np.loadtxt(out / "history.csv", delimiter=",", skiprows=1)
    column = {name: index for index, name in enumerate(header)}
    force = data[:, column["axle1_right_normal_n"]]
    pen = data[:, column["axle1_right_penetration_m"]]
    index = int(np.argmax(force))
    return {
        "c": level,
        "peak_kN": force[index] / 1e3,
        "x_m": float(data[index, column["axle1_x_m"]]),
        "pen_um": 1e6 * float(pen[index]),
        "elastic_kN": 1.1267e11 * float(pen[index]) ** 1.5 / 1e3,
        "min_kN": force.min() / 1e3,
        "lost": int(np.count_nonzero(force <= 0.0)),
    }


def main() -> int:
    print(f"{'c':>9}{'peak kN':>10}{'at x m':>9}{'pen um':>9}{'elastic kN':>12}"
          f"{'damp kN':>10}{'min kN':>9}{'lost':>6}")
    rows = []
    for level in LEVELS:
        row = run(level)
        rows.append(row)
        print(f"{row['c']:>9.0e}{row['peak_kN']:>10.1f}{row['x_m']:>9.2f}"
              f"{row['pen_um']:>9.0f}{row['elastic_kN']:>12.1f}"
              f"{row['peak_kN'] - row['elastic_kN']:>10.1f}"
              f"{row['min_kN']:>9.2f}{row['lost']:>6}")
    (BASE / "switch_damp.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
