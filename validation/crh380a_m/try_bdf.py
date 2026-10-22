"""S2 first cut: implicit BDF with a probed sparsity template.

The explicit DOP853 run of a 0.05 s frog window costs ~68 s and the stiff contact spring
forces ~1e-4 s steps. BDF with the true (sparse) Jacobian should take far fewer steps and
factorise a sparse matrix instead of probing it densely. This compares the two on the same
window and reports both cost and agreement.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_full12_cap05.json"
OUT = BASE / "out_implicit"

VARIANTS = (
    ("explicit", "DOP853", None),
    ("bdf_dense", "BDF", None),
    ("bdf_sparse", "BDF", "sparse_fd"),
)


def run(tag: str, method: str, jacobian: str | None) -> dict[str, float]:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    raw["case_id"] = f"imp_{tag}"
    raw["run"]["x_start_m"] = 69.0
    raw["run"]["duration_s"] = 0.05
    raw["run"]["method"] = method
    if jacobian is None:
        raw["run"].pop("jacobian", None)
    else:
        raw["run"]["jacobian"] = jacobian
    path = BASE / f"case_{raw['case_id']}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

    case = load_vehicle_case(path)
    start = time.perf_counter()
    result = simulate_vehicle(case)
    wall = time.perf_counter() - start
    save_vehicle_result(case, result, OUT / raw["case_id"])
    summary = result.summary
    return {
        "tag": tag,
        "method": method,
        "jacobian": jacobian,
        "wall_s": wall,
        "nfev": summary["solver"]["nfev"],
        "peak_kN": summary["peak_normal_force_n"]["axle1_right"] / 1e3,
        "maxpen_um": 1e6 * summary["max_penetration_m"],
        "status": summary["result_status"],
    }


def main() -> int:
    print(f"{'variant':>12}{'method':>9}{'wall s':>9}{'nfev':>9}{'peak kN':>10}"
          f"{'maxpen um':>11}  status")
    rows = []
    for tag, method, jacobian in VARIANTS:
        try:
            row = run(tag, method, jacobian)
        except Exception as error:  # noqa: BLE001 - report and continue
            print(f"{tag:>12}{method:>9}   failed: {type(error).__name__}: {error}")
            continue
        rows.append(row)
        print(f"{row['tag']:>12}{row['method']:>9}{row['wall_s']:>9.1f}{row['nfev']:>9}"
              f"{row['peak_kN']:>10.1f}{row['maxpen_um']:>11.1f}  {row['status']}")
    (BASE / "implicit_compare.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
