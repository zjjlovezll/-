"""What contact does the slope guard reject?  Prints y, normal and penetration for the first frame.

Run:  python -X utf8 scripts/s30e_guard_geometry.py --case PATH [--rail right] [--station 79]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

import velch.vehicle_solver as vs
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics

SPEED_KMH = 80.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    options = parser.parse_args()

    raw = json.loads(Path(options.case).read_text(encoding="utf-8"))
    raw["run"].update({"x_start_m": 69.0, "seat_x_start_m": 45.0, "duration_s": 0.01,
                       "output_step_s": 0.01, "method": "BDF", "jacobian": "analytic"})
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw.pop("initial_state", None)
    prepared = Path(options.case).with_name("case_guard.json")
    prepared.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    case = load_vehicle_case(prepared)
    dynamics = VehicleDynamics(case)
    velocity = np.zeros(dynamics.dimension)
    speed = SPEED_KMH / 3.6
    radius = float(case.vehicle.nominal_wheel_radius_m)
    for body in dynamics.topology.wheelsets():
        velocity[dynamics.topology.require(body.id, "spin")] = speed / radius

    original = vs.find_graph_contact
    printed: set[tuple[str, str]] = set()

    def traced(profile, sample, **kwargs):  # type: ignore[no-untyped-def]
        geometry = original(profile, sample, **kwargs)
        key = (str(getattr(sample.profile, "source", "?")), f"{kwargs.get('wheel_y_m', float('nan')):.3f}")
        if geometry is not None and key not in printed and len(printed) < 8:
            printed.add(key)
            print(f"\nprofile {str(profile.source)[:60]}")
            print(f"  wheel_y_m {float(kwargs['wheel_y_m']):+.5f} "
                  f"lateral_offset {float(kwargs['wheel_lateral_offset_m']):+.5f} "
                  f"roll {float(kwargs['wheel_roll_rad']):+.5f} "
                  f"rail_y_m {float(kwargs['rail_y_m']):+.5f} "
                  f"rail_z_m {float(kwargs['rail_z_m']):+.5f}")
            print(f"  -> y {float(geometry.y_m):+.5f} "
                  f"pen {float(geometry.penetration_m) * 1e6:+8.2f} um "
                  f"n_y {float(geometry.normal_y):+.4f} n_z {float(geometry.normal_z):+.4f} "
                  f"slope {abs(float(geometry.normal_y) / float(geometry.normal_z)):.4f}")
            print(f"     rail profile y {float(np.min(sample.profile.y_m)):+.4f}.."
                  f"{float(np.max(sample.profile.y_m)):+.4f} "
                  f"z {float(np.min(sample.profile.z_m)):+.5f}..{float(np.max(sample.profile.z_m)):+.5f}")
        return geometry

    vs.find_graph_contact = traced
    try:
        dynamics.placement_enabled = False
        dynamics.evaluate(0.0, np.zeros(dynamics.dimension), velocity)
        print("\nno failure")
    except Exception as error:  # noqa: BLE001 - the point is to report it
        print(f"\n{type(error).__name__}: {error}")
    finally:
        vs.find_graph_contact = original
    return 0


if __name__ == "__main__":
    sys.exit(main())
