"""Cost per contact-geometry call under each geometry policy, and the accuracy it costs.

A speed figure is only worth having if the answer survives, so every policy is
compared against the historical merged-grid path on the same state.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_Z_local_rail.json"
POLICIES = (("grid", 0.0, "window"),
            ("cached_grid", 5.0e-4, "window"),
            ("cached_grid", 5.0e-4, "grid_stencil"),
            ("cached_grid", 2.5e-4, "grid_stencil"))


def variant(policy: str, step: float, curvature: str, states: int = 240):
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    raw["contact"]["geometry_policy"] = policy
    raw["contact"]["grid_step_m"] = float(step)
    raw["contact"]["curvature_policy"] = curvature
    raw["case_id"] = f"bench_{policy}_{step:g}_{curvature}"
    path = BASE / f"case_bench_{policy}_{step:g}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    case = load_vehicle_case(path)
    dynamics = VehicleDynamics(case)
    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    # Contacting state: sink every axle by 0.6 mm so the search has a real extremum
    # to find instead of an empty band.
    for axle in range(4):
        q[5 * axle + 1] -= 6.0e-4
    geometry = None
    dynamics.evaluate(0.0, q, v)
    count = sum(len(rail.contact_bodies) for rail in case.rails)
    start = time.perf_counter()
    for _ in range(states):
        _, contacts = dynamics.evaluate(0.0, q, v)
    per_rhs = (time.perf_counter() - start) / states
    geometry = {name: (response.geometry.penetration_m if response.geometry else None,
                       response.geometry.y_m if response.geometry else None)
                for name, response in contacts.items()}
    dynamics.close()
    return per_rhs, per_rhs / count, geometry, count


def main() -> int:
    reference = None
    print(f"{'policy':<14}{'step mm':>9}{'curvature':>12}{'RHS us':>10}{'per-call us':>13}"
          f"{'dpen um':>10}{'dy mm':>9}")
    for policy, step, curvature in POLICIES:
        per_rhs, per_call, values, count = variant(policy, step, curvature)
        if reference is None:
            dpen = dy = 0.0
            reference = values
        else:
            dpen = dy = 0.0
            for name, (pen, y) in values.items():
                ref_pen, ref_y = reference[name]
                if pen is None or ref_pen is None:
                    continue
                dpen = max(dpen, abs(pen - ref_pen))
                dy = max(dy, abs(y - ref_y))
        print(f"{policy:<14}{1e3 * step:>9.2f}{curvature:>12}{1e6 * per_rhs:>10.1f}"
              f"{1e6 * per_call:>13.1f}{1e6 * dpen:>10.2f}{1e3 * dy:>9.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
