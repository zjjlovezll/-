"""Does the contact plane's tilt respond to a lateral shift, and how fast?

The capacity sweep (`scripts/s43_running_equilibrium.py --capability`) found the strongest state
that keeps all eight wheels inside the acceptance band delivers 8.17 kN of the 21.8 kN a cant-free
R = 1100 m curve at 80 km/h needs, and that reaching the demand costs a whole side of contact.
Its conclusion rests on one number: the contact plane's tilt ``n_y / n_z = +-0.0250``.

That tilt was measured constant against *rail height* offsets (s36b, seven points, 0.0 um spread),
but it has never been measured against a *lateral* shift -- the displacement a curving vehicle
actually makes.  This probe measures it: shift every wheelset laterally, re-seat the vertical rows
so the loads stay at one vehicle weight, and read each contact's tilt, lever arm and net lateral
force.  Two readings follow:

* ``d(n_y/n_z)/dy``: how fast the geometry can respond at all;
* whether that rate could lift the in-band capability to the demand.

Pre-registered, before the numbers: if the tilt grows fast enough that the band limit reaches
``>= 1.0 x demand``, the "in band is impossible" conclusion is refuted and the contact geometry --
not cant -- is what has to be fixed.  Otherwise cant (or flange contact as new physics) is the only
route, and the curve item stays degraded.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics, _load_per_wheel, _seat  # noqa: E402

SCRATCH = REPO.parent / "scratch" / "s44"
EVEN_SHARE_N = 59_662.0


def _s43():
    spec = importlib.util.spec_from_file_location(
        "s43_running_equilibrium", REPO / "scripts" / "s43_running_equilibrium.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radius", type=float, default=1100.0)
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    parser.add_argument("--run-at", type=float, default=30.0)
    parser.add_argument("--shift-mm", type=float, default=3.0)
    parser.add_argument("--step-mm", type=float, default=0.25)
    args = parser.parse_args(argv)

    s43 = _s43()
    path = s43.build_case(radius_m=args.radius, speed_kmh=args.speed_kmh,
                          run_at_m=args.run_at, seat_at_m=args.run_at,
                          creep_scale=1.0, duration_s=0.02)
    case = load_vehicle_case(path)
    dynamics = VehicleDynamics(case)
    speed = float(case.vehicle.travel_speed_m_s)
    mass = sum(body.mass_kg for body in dynamics.topology.bodies)
    demand_n = mass * speed * speed / args.radius
    print(f"{path.name}: R {args.radius:.0f} m, {args.speed_kmh:.1f} km/h, demand {demand_n:.1f} N")

    zeros = np.zeros(dynamics.dimension)
    velocity = np.zeros(dynamics.dimension)
    radius_wheel = float(case.vehicle.nominal_wheel_radius_m)
    for body in dynamics.topology.wheelsets():
        velocity[dynamics.topology.require(body.id, "spin")] = speed / radius_wheel
    seated, residual = _seat(case, dynamics, zeros, velocity)
    print(f"seat residual {residual:.3e} N\n")

    count = int(round(2 * args.shift_mm / args.step_mm)) + 1
    offsets = [(-args.shift_mm + index * args.step_mm) for index in range(count)]
    rows: list[dict] = []
    print("  shift   tiltL      tiltR    d(tilt)/dy   leverL    leverR    sum Fy     share     pen")
    print("   mm                                                            N          %      um")
    for offset in offsets:
        trial = seated.copy()
        for body in dynamics.topology.wheelsets():
            if "y" in body.dof:
                trial[dynamics.topology.require(body.id, "y")] += offset * 1e-3
        # Re-seat the vertical rows so the loads stay at one vehicle weight: the question is what
        # the *geometry* offers, not how much the rail is squashed.
        settled, error_n, _, _ = s43.solve_frame_equilibrium(case, dynamics, trial, velocity,
                                                            include_lateral=False)
        _, contacts = dynamics.evaluate(0.0, settled, velocity)
        left = [contacts[rail.id] for rail in case.rails
                if rail.id.endswith("left") and contacts.get(rail.id) is not None
                and contacts[rail.id].geometry is not None]
        right = [contacts[rail.id] for rail in case.rails
                 if rail.id.endswith("right") and contacts.get(rail.id) is not None
                 and contacts[rail.id].geometry is not None]
        if not left or not right:
            print(f"  {offset:+6.2f}   contact missing on one side")
            continue
        tilt_left = float(np.mean([response.geometry.normal_y / response.geometry.normal_z
                                   for response in left]))
        tilt_right = float(np.mean([response.geometry.normal_y / response.geometry.normal_z
                                    for response in right]))
        lever_left = float(np.mean([response.geometry.lever_y_m for response in left]))
        lever_right = float(np.mean([response.geometry.lever_y_m for response in right]))
        loads = {rail.id: float(contacts[rail.id].normal_force_n)
                 for rail in case.rails if contacts.get(rail.id) is not None}
        per_wheel = _load_per_wheel(case.rails, [loads.get(rail.id, 0.0) for rail in case.rails])
        ratios = [value / EVEN_SHARE_N for value in per_wheel.values()]
        total_fy = sum(float(response.wheel_force_y_n)
                       for response in left + right)
        penetration = max(float(response.geometry.penetration_m) for response in left + right)
        inside = min(ratios) >= 0.625 and max(ratios) <= 1.6
        print(f"  {offset:+6.2f}  {tilt_left:+.5f}  {tilt_right:+.5f}              "
              f"{lever_left:+.5f}  {lever_right:+.5f}  {total_fy:+9.1f}  "
              f"{total_fy / demand_n * 100:+6.1f}  {penetration * 1e6:7.2f}"
              f"{'  in band' if inside else '  OUT'}   (|r|z {error_n:.1e} N)")
        rows.append({"offset_mm": offset, "tilt_left": tilt_left, "tilt_right": tilt_right,
                     "lever_y_left": lever_left, "lever_y_right": lever_right,
                     "sum_fy_n": total_fy, "in_band": bool(inside),
                     "max_penetration_m": penetration,
                     "vertical_residual_n": error_n, "ratios": ratios})

    if len(rows) < 4:
        print("\nnot enough in-contact states to fit a slope")
        return 2
    shifts = np.array([row["offset_mm"] for row in rows]) * 1e-3
    tilt = np.array([0.5 * (row["tilt_left"] - row["tilt_right"]) for row in rows])
    slope, intercept = np.polyfit(shifts, tilt, 1)
    lever = np.array([0.5 * (row["lever_y_right"] - row["lever_y_left"]) for row in rows])
    lever_slope = float(np.polyfit(shifts, lever, 1)[0])
    print(f"\nd(n_y/n_z)/dy  {slope:+.3f} 1/m      (intercept {intercept:+.5f})")
    print(f"d(lever_y)/dy  {lever_slope:+.5f} m/m")
    band = [row for row in rows if row["in_band"]]
    best = max((abs(row["sum_fy_n"]) for row in band), default=0.0)
    print(f"best in-band |sum Fy| {best:.1f} N = {best / demand_n * 100:.1f} % of demand")
    verdict = ("BAND CAN CARRY THE CURVE" if best >= demand_n else
               "BAND STILL SHORT: geometry rate does not rescue it")
    print(f"VERDICT {verdict}")

    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / "tilt_sensitivity.json").write_text(json.dumps({
        "case": path.name, "radius_m": args.radius, "speed_kmh": args.speed_kmh,
        "demand_n": demand_n, "seat_residual_n": residual,
        "rows": rows, "tilt_slope_1_per_m": float(slope), "lever_slope": lever_slope,
        "best_in_band_fy_n": best, "verdict": verdict,
    }, indent=1), encoding="utf-8")
    return 0 if best >= demand_n else 2


if __name__ == "__main__":
    sys.exit(main())
