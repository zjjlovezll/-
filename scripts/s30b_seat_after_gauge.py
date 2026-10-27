"""Seated contact table of the rebuilt diverging case (B041) at the start of the 80 km/h run.

Before B041 the right rail centre drifted up to +64 mm off the left's design line (gauge 1.444-1.588 m
against the wheels' 1.493 m), and the seated first frame read ``axle3_right 160.5 kN = 2.69x`` with
120.6 um penetration while ``axle1_right`` / ``axle2_right`` found no contact.  This prints the same
table after the rebuild so the two can be compared line for line.

Run:  python -X utf8 scripts/s30b_seat_after_gauge.py [--duration 0.0]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat, simulate_vehicle

SPEED_KMH = 80.0
SEAT_AT_M = 45.0
EVEN_SHARE_N = 59_662.0
CASE = Path(__file__).resolve().parents[2] / "scratch" / "s30" / "case_diverging_gauge.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=0.0,
                        help="0 = probe the seated first frame only; >0 also integrates")
    parser.add_argument("--method", default="BDF")
    options = parser.parse_args()

    raw = json.loads(CASE.read_text(encoding="utf-8"))
    raw["run"].update({"seat_x_start_m": SEAT_AT_M, "method": options.method,
                       "jacobian": "analytic" if options.method != "DOP853" else None})
    raw["run"]["duration_s"] = max(options.duration, 0.01)
    raw["run"]["output_step_s"] = min(5e-4, max(options.duration, 1e-3))
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw.pop("initial_state", None)
    prepared = CASE.with_name("case_diverging_gauge_probe.json")
    prepared.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    case = load_vehicle_case(prepared)

    dynamics = VehicleDynamics(case)
    speed = SPEED_KMH / 3.6
    velocity = np.zeros(dynamics.dimension)
    radius = float(case.vehicle.nominal_wheel_radius_m)
    for body in dynamics.topology.wheelsets():
        velocity[dynamics.topology.require(body.id, "spin")] = speed / radius
    seated, residual = _seat(case, dynamics, np.zeros(dynamics.dimension), velocity)
    _, contacts = dynamics.evaluate(0.0, seated, velocity)
    print(f"coordinates {dynamics.dimension}, seat residual {residual:.3e} N")
    total = 0.0
    loaded = 0
    for key, value in sorted(contacts.items()):
        geometry = value.geometry
        if geometry is None:
            print(f"    {key:<14s} no geometry")
            continue
        loaded += 1
        total += float(value.normal_force_n)
        print(f"    {key:<14s} N {float(value.normal_force_n):9.1f} "
              f"({float(value.normal_force_n) / EVEN_SHARE_N:5.3f}x)  "
              f"pen {float(geometry.penetration_m) * 1e6:7.2f} um  "
              f"lever_y {float(geometry.lever_y_m):+8.5f}  "
              f"Fy {float(value.wheel_force_y_n):+9.1f}  "
              f"slip_lat {float(value.slip_lateral_m_s):+.5f}")
    mass = sum(body.mass_kg for body in dynamics.topology.bodies)
    print(f"loaded {loaded}/{len(contacts)}  sum N {total:.1f} N "
          f"({total / (8 * EVEN_SHARE_N):.3f}x of the weight)  "
          f"sum Fy {sum(float(c.wheel_force_y_n) for c in contacts.values() if c.geometry):+.1f} N  "
          f"centripetal {mass * speed * speed / 1100.0:+.1f} N")

    if options.duration > 0.0:
        result = simulate_vehicle(case)
        summary = result.summary
        print(f"\nrun {options.duration:.3f} s -> {summary['result_status']}")
        for gate in summary["gates"]:
            state = "pass" if gate["passed"] else "FAIL"
            print(f"    {gate['name']:<34s} {state}  {gate.get('detail', '')}")
        print(f"    max penetration {float(summary['max_penetration_m']) * 1e6:.2f} um, "
              f"{len(result.times_s)} frames, end mileage "
              f"{float(result.summary.get('end_mileage_m', float('nan'))):.3f} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
