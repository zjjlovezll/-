"""Print the geometry the contact slope guard rejects, then hand the call back unchanged.

The straight-route seat now fails with ``graph slope limit at axle1_right/right:stock, x=50 m`` even
with the switch blade switched off, so the guard is rejecting the *plain* through-route contact.  The
guard's message names the rail and the mileage but not the geometry, and the geometry is the whole
question: a wheel 13 mm from the crown cannot have ``|n_y / n_z| > 1``.  This wraps
``velch.vehicle_solver.find_graph_contact`` only to print what came back; the search itself, the guard
and every tolerance stay exactly as shipped.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from velch import vehicle_solver
from velch.vehicle import load_vehicle_case

ORIGINAL = vehicle_solver.find_graph_contact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=6)
    options = parser.parse_args()

    printed: list[str] = []

    def traced(*args, **kwargs):
        geometry = ORIGINAL(*args, **kwargs)
        if geometry is None:
            return geometry
        slope = abs(float(geometry.normal_y) / float(geometry.normal_z)) if geometry.normal_z else float("inf")
        if slope > 1.0 and len(printed) < options.limit:
            printed.append(
                f"  slope {slope:6.3f}  lever_y {float(geometry.lever_y_m):+.5f} m"
                f"  lever_z {float(geometry.lever_z_m):+.5f} m"
                f"  pen {float(geometry.penetration_m) * 1e6:+9.2f} um"
                f"  n_y {float(geometry.normal_y):+.4f} n_z {float(geometry.normal_z):+.4f}"
            )
        return geometry

    vehicle_solver.find_graph_contact = traced
    case = load_vehicle_case(options.case)
    dynamics = vehicle_solver.VehicleDynamics(case)
    q = np.zeros(dynamics.dimension)
    v = np.zeros(dynamics.dimension)
    try:
        dynamics.evaluate(0.0, q, v)
    except Exception as exc:
        print(f"refused: {type(exc).__name__}: {str(exc)[:120]}")
    print("\n".join(printed) if printed else "  no steep contact was produced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
