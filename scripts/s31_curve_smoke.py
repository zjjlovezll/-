"""Can a *symmetric* straight station table be run as a curve, so that the corrugation
experiment does not have to fight the diverging case's two incompatible rail sources?

B041 measured that ``case_diverging_R1100.json`` glues two different models together: the left
rail is ``Profile_Mileage_JBG.prr`` (CRH380A) and the right one ``jbg-20200418-R.prr`` (SDITT
07(009)), so the gauge wanders 1.4438..1.5876 m while the wheels are placed at 1.493 m and the
right wheel rides the gauge corner (measured 2.69x even share).  Rebuilding the right side with a
constant offset did not fix it (1.4796 -> 15.5 mm, 1.493 -> 3.1 mm, 1.5065 -> 626 um at 79 m),
which says the right rail's cross-section itself changes along that route.

This script takes the opposite road: ``case_A_final_law`` is one symmetric straight track with a
rigid kernel, and the curvature is put in through ``curve_radius_m`` + ``curve_geometry`` (the
route that already passes 7/7 with cant = 0).  Both rails then come from the same source, the
gauge is exactly the wheels' 1.493 m by construction, and the only curved physics in play is the
placement of the track and the vehicle plus the curvature term in ``slip_x``.

Run:  python -X utf8 scripts/s31_curve_smoke.py [--duration 0.02] [--radius 1100] [--kmh 80]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import (_align_to_track_frame, _place_on_alignment, _seat,
                                  simulate_vehicle)

EVEN_SHARE_N = 59_662.0


def build(*, radius_m: float, speed_kmh: float, duration_s: float, x_start_m: float,
          name: str) -> Path:
    raw = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
    raw["case_id"] = name
    raw["run"].update({
        "x_start_m": x_start_m,
        "seat_x_start_m": x_start_m,
        "duration_s": duration_s,
        "output_step_s": 2.0e-4,
        "max_solver_step_s": 1.0e-4,
        "curve_radius_m": radius_m,
        "curve_geometry": True,
        "align_to_track": True,
    })
    raw["run"].pop("curve_cant_m", None)
    raw["vehicle"]["travel_speed_m_s"] = speed_kmh / 3.6
    raw.pop("initial_state", None)
    raw.pop("irregularity", None)
    target = Path(__file__).resolve().parents[2] / "scratch" / "s31" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return target


def frame_table(dynamics, q, v) -> None:
    """The seated state's contact set, printed the way every earlier probe printed it."""
    force, contacts = dynamics.evaluate(0.0, q, v)
    weight = float(sum(getattr(b, "mass_kg", 0.0) for b in dynamics.topology.bodies)) * 9.81
    total = 0.0
    for rail in dynamics.case.rails:
        response = contacts.get(rail.id)
        if response is None or response.geometry is None:
            print(f"    {rail.id:<14} no geometry")
            continue
        geometry = response.geometry
        ratio = response.normal_force_n / EVEN_SHARE_N
        total += response.normal_force_n
        print(f"    {rail.id:<14} N {response.normal_force_n:9.1f} ({ratio:5.3f}x) "
              f"pen {geometry.penetration_m * 1e6:8.2f} um "
              f"lever_y {geometry.lever_y_m:+.5f} "
              f"n_y/n_z {geometry.normal_y / geometry.normal_z:+.4f} "
              f"slip_lat {response.slip_lateral_m_s:+.4f}")
    print(f"    sum N {total:.1f} N ({total / weight:.3f}x weight)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=0.02)
    parser.add_argument("--radius", type=float, default=1100.0)
    parser.add_argument("--kmh", type=float, default=80.0)
    parser.add_argument("--x-start", type=float, default=30.0)
    args = parser.parse_args(argv)

    name = f"case_curve_r{args.radius:.0f}_{args.kmh:.0f}.json"
    path = build(radius_m=args.radius, speed_kmh=args.kmh,
                 duration_s=args.duration, x_start_m=args.x_start, name=name)
    case = load_vehicle_case(path)
    print(f"case {path.name}  radius {args.radius} m  {args.kmh} km/h  from {args.x_start} m")
    from velch.vehicle_solver import VehicleDynamics
    dynamics = VehicleDynamics(case)
    print(f"  coordinates {dynamics.dimension}  rails {len(case.rails)}  "
          f"templates {sorted({str(r.template_id) for r in case.rails})}")
    velocity = np.zeros(dynamics.dimension)
    seated, residual = _seat(case, dynamics, np.zeros(dynamics.dimension), velocity)
    print(f"  seat residual {residual:.3e} N")
    # Same order as ``_integrate_vehicle``: the seat solves against the equivalent straight, then
    # the vehicle is set on the design line it will run along.  Comparing the two without this step
    # leaves the rails placed 45 mm out from under a vehicle solved straight, and the frame table
    # then reads 27 mm of penetration on four rails and no contact at all on the other four.
    if bool(getattr(case.run, "align_to_track", False)):
        seated = _place_on_alignment(case, dynamics, seated)
        seated = _align_to_track_frame(case, dynamics, seated)
    frame_table(dynamics, seated, velocity)

    if args.duration > 0.0:
        result = simulate_vehicle(case)
        summary = result.summary
        print(f"  run {summary['result_status']}  frames {result.positions.shape[0]}")
        failed = [name for name, ok in summary["gates"].items() if not ok]
        print(f"  gates {sum(1 for ok in summary['gates'].values() if ok)}"
              f"/{len(summary['gates'])} failing {failed}")
        print(f"  max penetration {summary['max_penetration_m'] * 1e6:.2f} um  "
              f"peaks {summary['peak_normal_force_n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
