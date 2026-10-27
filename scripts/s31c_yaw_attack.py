"""Does the alignment's absolute heading, read by the creep law as an angle of attack, drift the
vehicle off a curved route?

``_align_to_track_frame`` writes ``q[yaw] = atan(dy/ds)`` -- the *absolute* heading of the design
line, 9.09 mrad at the leading axle of a 20 m footprint on R = 1100 m.  The creep law reads the
same coordinate as an angle of attack (``creep_attack_velocity_m_s = travel * q[yaw]``), so an
aligned vehicle starts with ``travel * yaw = 0.202 m/s`` of spurious lateral creep at axle 1.

The clean case built by :mod:`s31_curve_smoke` (symmetric station table, one rail source, 8/8
wheels at 0.988..1.013x) survives 0.02 s but dies on the contact-slope guard after 1.04 m of
travel.  This probe holds everything fixed and only zeroes the yaw *after* the alignment, which
is equivalent to "the vehicle's heading relative to its own rail is zero" -- the state a vehicle
that follows the curve is in.  Nothing in the contact geometry reads ``yaw`` (the strip search is
two dimensional in (y, z)), so zeroing it changes the creep term and nothing else.

Run:  python -X utf8 scripts/s31c_yaw_attack.py [--duration 0.30] [--variant as-is|zero-yaw]
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

import s31b_curve_corrugation as protocol

from velch import vehicle_solver
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

_ORIGINAL = vehicle_solver._align_to_track_frame


def zero_yaw(case, dynamics, q):
    """Place the vehicle on the design line laterally, but keep every body's heading at zero."""
    placed = _ORIGINAL(case, dynamics, q)
    out = np.array(placed, dtype=float)
    for body in dynamics.topology.bodies:
        try:
            index = dynamics.topology.require(body.id, "yaw")
        except KeyError:
            continue
        out[index] = 0.0
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=0.30)
    parser.add_argument("--variant", choices=("as-is", "zero-yaw", "both"), default="both")
    args = parser.parse_args(argv)

    variants = ("as-is", "zero-yaw") if args.variant == "both" else (args.variant,)
    for variant in variants:
        vehicle_solver._align_to_track_frame = _ORIGINAL if variant == "as-is" else zero_yaw
        path = protocol.build_case(duration_s=args.duration, name=f"case_yaw_{variant}.json")
        case = load_vehicle_case(path)
        print(f"variant {variant}  R {protocol.RADIUS_M} m  {protocol.SPEED_KMH} km/h  "
              f"{args.duration} s")
        try:
            result = simulate_vehicle(case)
        except Exception as error:  # the guard is a legitimate outcome, report it
            print(f"  FAILED -- {error}")
            continue
        summary = result.summary
        failing = [gate for gate, ok in summary["gates"].items() if not ok]
        peaks = summary["peak_normal_force_n"]
        worst = max(peaks.values()) / 59_662.0
        print(f"  {summary['result_status']}  frames {result.positions.shape[0]}  "
              f"end mileage {result.positions[-1, 0]:.3f} m")
        print(f"  gates {sum(1 for ok in summary['gates'].values() if ok)}"
              f"/{len(summary['gates'])} failing {failing}")
        print(f"  worst share {worst:.3f}x  max penetration "
              f"{summary['max_penetration_m'] * 1e6:.1f} um")
        lateral = [name for name in result.acceleration_names if "y_acc" in name][:4]
        print(f"  lateral acceleration channels: {lateral}")
    vehicle_solver._align_to_track_frame = _ORIGINAL
    return 0


if __name__ == "__main__":
    sys.exit(main())
