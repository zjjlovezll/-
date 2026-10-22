"""Which rail carries nothing at t=0?  Prints the merged per-rail contact state."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics  # noqa: E402


def main(path: str) -> int:
    case = load_vehicle_case(HERE / path)
    dynamics = VehicleDynamics(case)
    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    force, contacts = dynamics.evaluate(0.0, q, v)
    print(f"case {case.case_id}: x_start {case.run.x_start_m:.2f} m, "
          f"path = {case.path.at(case.run.x_start_m) * 1e3:.1f} mm at the carbody\n")
    print(f"{'rail':<14} {'x (m)':>8} {'path mm':>8} {'N (kN)':>9} {'pen (µm)':>9} "
          f"{'contact y (mm)':>15} {'edge':>5}")
    for rail in case.rails:
        response = contacts[rail.id]
        geometry = response.geometry
        axle = rail.axle_index
        station = case.run.x_start_m + case.vehicle.axle_offsets_m[axle]
        print(f"{rail.id:<14} {station:8.2f} {case.path.at(station) * 1e3:8.1f} "
              f"{response.normal_force_n / 1e3:9.2f} "
              f"{(geometry.penetration_m * 1e6 if geometry else float('nan')):9.1f} "
              f"{(geometry.y_m * 1e3 if geometry else float('nan')):15.1f} "
              f"{str(geometry.edge_limited) if geometry else '-':>5}")
    vertical = force[[5 * i + 1 for i in range(4)] + [21, 26, 31]]
    print(f"\nvertical residual (N): {np.round(vertical, 1)}")
    dynamics.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
