"""Is the route's lateral *rate* being fed into the creep as if the wheel were sliding?

``vehicle_solver.py:646-647`` transports the wheel along the case's ``path`` -- its position offset
``path.at(x)`` is added to the wheel's lateral offset -- and then also adds the path's lateral
**rate** ``v * dy/ds`` to the wheel's lateral velocity.  The comment says that slope "is a lateral
creepage", and that is the claim under test.

It cannot be right: a vehicle that follows a curve has ``dq[y]/dt = 0`` relative to the rail and
therefore no lateral creep, while ``v * dy/ds`` is 0.57 m/s at 80 km/h on this route.  On the 18
turnout that is what the logs show -- ``slip_lat`` is 0.52..0.57 m/s at t = 0 with every velocity
in the state equal to zero apart from the spin -- and the contact then saturates, shoves the
wheelset inboard, and trips ``graph slope limit`` at 81.29 m.

The experiment holds everything else fixed: the same case, the same run, once with the rate as it
is and once with the rate forced to zero.  What has to change is the first-frame ``slip_lat`` (0.57
-> 0) and whether the run reaches the end of the corrugation patch at 83.6 m.

Run:  python -X utf8 scripts/s29_path_rate.py [--duration 0.20]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from velch import data_root
from velch.paths import PathTrack as RoutePath
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, simulate_vehicle

SPEED_KMH = 80.0
SEAT_AT_M = 45.0
RUN_AT_M = 69.0
EVEN_SHARE_N = 59_662.0


def build(duration_s: float, name: str):
    raw = json.loads((data_root.case_dir() / "case_diverging_R1100.json").read_text(encoding="utf-8"))
    raw["run"].update({
        "x_start_m": RUN_AT_M,
        "seat_x_start_m": SEAT_AT_M,
        "duration_s": duration_s,
        "output_step_s": 5e-4,
        "max_solver_step_s": 5e-4,
        "method": "BDF",
        "jacobian": "analytic",
    })
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw.pop("initial_state", None)
    raw.pop("irregularity", None)
    target = Path(__file__).resolve().parents[2] / "scratch" / "s29" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return load_vehicle_case(target)


def first_frame_slip(case) -> str:
    dynamics = VehicleDynamics(case)
    speed = SPEED_KMH / 3.6
    q = np.zeros(dynamics.dimension)
    v = np.zeros(dynamics.dimension)
    for body in dynamics.topology.wheelsets():
        v[dynamics.topology.require(body.id, "spin")] = speed / float(case.vehicle.nominal_wheel_radius_m)
    _, contacts = dynamics.evaluate(0.0, q, v)
    slips = [float(item.slip_lateral_m_s) for item in contacts.values() if item.geometry is not None]
    if not slips:
        return "no contact"
    return f"{min(slips):+.4f}..{max(slips):+.4f} m/s over {len(slips)} patches"


def run(label: str, duration_s: float, zero_rate: bool) -> None:
    case = build(duration_s, f"case_{label}.json")
    original = RoutePath.lateral_velocity_m_s
    print(f"\n=== path lateral rate {'forced to zero' if zero_rate else 'as shipped'} ===")
    try:
        if zero_rate:
            RoutePath.lateral_velocity_m_s = lambda self, station_m, speed_m_s: 0.0
        print(f"first-frame slip_lateral : {first_frame_slip(case)}")
        result = simulate_vehicle(case)
        summary = result.summary
        failed = [name for name, value in summary["gates"].items() if not bool(value)]
        print(f"status                   : {summary['result_status']}")
        print(f"gates                    : {len(summary['gates']) - len(failed)}"
              f"/{len(summary['gates'])}"
              + (f"   failed {failed}" if failed else ""))
        peak = summary["peak_normal_force_n"]
        if isinstance(peak, dict):
            print("peak normal per patch    : "
                  + ", ".join(f"{key} {float(value):.0f} N ({float(value) / EVEN_SHARE_N:.2f}x)"
                              for key, value in sorted(peak.items())))
        print(f"max penetration          : {float(summary['max_penetration_m']) * 1e6:.2f} um")
        print(f"frames / end mileage     : {len(result.times_s)} / "
              f"{RUN_AT_M + SPEED_KMH / 3.6 * duration_s:.2f} m")
    except Exception as error:  # noqa: BLE001 - the failure text is the result here
        print(f"status                   : FAILED -- {error}")
    finally:
        RoutePath.lateral_velocity_m_s = original


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=0.20)
    options = parser.parse_args()
    run("as_shipped", options.duration, False)
    run("rate_zeroed", options.duration, True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
