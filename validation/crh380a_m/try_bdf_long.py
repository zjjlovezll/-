"""Does implicit BDF survive the frog body switch at all?

The 0.05 s window stops at x = 73.9 m and never reaches the frog (79.1 m), so its success
says nothing about the switch. This runs 0.2 s (x = 69 .. 88.4 m) with BDF, with and
without the sparsity template, to separate "the template is wrong" from "BDF cannot cross
a contact topology change".
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_full12_cap05.json"


def run(tag: str, jacobian: str | None) -> None:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    raw["case_id"] = f"frog_long_{tag}"
    raw["run"]["x_start_m"] = 69.0
    raw["run"]["duration_s"] = 0.2
    raw["run"]["method"] = "BDF"
    if jacobian is None:
        raw["run"].pop("jacobian", None)
    else:
        raw["run"]["jacobian"] = jacobian
    path = BASE / f"case_{raw['case_id']}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    case = load_vehicle_case(path)
    start = time.perf_counter()
    try:
        result = simulate_vehicle(case)
    except Exception as error:  # noqa: BLE001 - the point is to report the failure
        print(f"{tag:>12}  failed after {time.perf_counter() - start:6.1f} s: "
              f"{type(error).__name__}: {error}")
        return
    wall = time.perf_counter() - start
    summary = result.summary
    print(f"{tag:>12}  {wall:6.1f} s  nfev {summary['solver']['nfev']:>7}  "
          f"peak {summary['peak_normal_force_n']['axle1_right'] / 1e3:6.1f} kN  "
          f"maxpen {1e6 * summary['max_penetration_m']:6.1f} um  {summary['result_status']}")


if __name__ == "__main__":
    run("bdf_dense", None)
    run("bdf_sparse", "sparse_fd")
