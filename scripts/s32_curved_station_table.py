"""A curved route written into the station table, on a case whose two rails are one track.

The `curve_radius_m` + `curve_geometry` route moves the *rail* sideways under the vehicle as the
mileage grows (`local_state` returns `speed * dy_ds`), and the measurements say that route cannot
hold R = 1100 m at 80 km/h: the crown contact at 65.47 um delivers `n_y/n_z = 0.025`, i.e.
1.49 kN per patch, 11.9 kN over eight patches, against the 21 842.4 N the curve needs.  The wheels
then climb the section until the slope guard sees the flange (1.0423 at 413 um penetration, 1.20 m
into the run).

The turnout cases do not have that problem because their curve is *static geometry*: each station
carries its own lateral offset, and a `path` table carries the vehicle along the same line.  This
script builds that arrangement on a case whose two rails come from one source
(``case_A_final_law``: rigid, both templates read ``Profile_Mileage_JBG.prr``, gauge 1.493 m), so
the curved route can be measured without B041's two-model defect:

* every station's ``y_offset_m`` becomes ``-0.753 + y_route(x)`` (left) / ``+0.753 + y_route(x)``;
* ``path`` gets the same ``y_route``, which is what transports the wheel (``lateral_extra``);
* ``y_route(x) = max(x - tangent, 0) ** 2 / (2R)``, so the seat can stand on the straight approach.

Run:  python -X utf8 scripts/s32_curved_station_table.py [--duration 0.05] [--radius 1100]
                                                    [--tangent 30] [--run-at 30] [--seat-at 30]
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
from velch.vehicle_solver import VehicleDynamics, simulate_vehicle

SPEED_KMH = 80.0
EVEN_SHARE_N = 59_662.0
OUT = Path(__file__).resolve().parents[2] / "scratch" / "s32"


def y_route(x: np.ndarray | float, tangent_m: float, radius_m: float):
    """Design-line offset with a clamped tangent: zero before the tangent, quadratic after it."""

    values = np.maximum(np.asarray(x, dtype=float) - float(tangent_m), 0.0)
    return values * values / (2.0 * float(radius_m))


def build(*, radius_m: float, tangent_m: float, step_m: float, span_m: float,
          duration_s: float, run_at_m: float, seat_at_m: float,
          curvature_force: bool = False,
          primary_lateral_damping: tuple[float, float] | None = None,
          creep_scale: float | None = None) -> Path:
    raw = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
    raw.pop("initial_state", None)
    raw["case_id"] = f"curved_station_table_R{radius_m:.0f}"
    raw["purpose"] = "synthetic"
    raw["purpose_detail"] = ("B041-free curve: both rails read the same PRR file, the route lives in "
                             "the station offsets and in `path`, and no placement is used.")
    count = int(round(span_m / step_m)) + 1
    stations_m = step_m * np.arange(count)
    route = y_route(stations_m, tangent_m, radius_m)
    for spec in raw["rail_templates"]:
        base = -0.753 if float(spec["stations"][0]["profile"]["y_offset_m"]) < 0.0 else 0.753
        template = spec["stations"][0]["profile"]
        spec["stations"] = [
            {
                "s_m": float(stations_m[index]),
                "id": f"{spec['id'][0].upper()}{index}",
                "profile": {**template, "y_offset_m": float(base + route[index])},
            }
            for index in range(count)
        ]
    # The path is what carries the wheel: `_evaluate_patch` adds `path.at(x)` to the lateral offset.
    path_step = 0.1
    path_count = int(round(span_m / path_step)) + 1
    path_stations = path_step * np.arange(path_count)
    raw["path"] = {
        "stations_s_m": [float(value) for value in path_stations],
        "y_m": [float(value) for value in y_route(path_stations, tangent_m, radius_m)],
    }
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    if creep_scale is not None:
        # DIAGNOSTIC ONLY, never the acceptance case: the frozen law carries f11 = 1e6 N and
        # f22 = 5e5 N, roughly a decade below the physical creep coefficients of a 60 kN wheel-rail
        # contact (5-10 MN).  Scaling them is *not* a repair of a failure -- it is a separate
        # question ("would a physical creep law steer this curve?") and the emitted case records
        # the factor so a run can never be quoted without it.  `creep_scale = 10` gives
        # f11 = 1e7, f22 = 5e6.
        contact = raw["contact"]
        contact["creep_stiffness_x_n"] = float(contact["creep_stiffness_x_n"]) * float(creep_scale)
        contact["creep_stiffness_lateral_n"] = (float(contact["creep_stiffness_lateral_n"])
                                                * float(creep_scale))
    if primary_lateral_damping is not None:
        # The inline vehicle carries `c_y = 0` and `c_yaw = 0`, so the lateral and yaw modes are
        # damped only by the creep law.  A real bogie has an axle-box arm bushing and a lateral
        # damper; this option exists to *measure* whether any plausible value settles the curve,
        # and the emitted case records the value so the run cannot be quoted without it.
        c_y, c_yaw = (float(value) for value in primary_lateral_damping)
        raw["vehicle"]["primary"]["c_y_n_s_m"] = c_y
        raw["vehicle"]["primary"]["c_yaw_nm_s_rad"] = c_yaw
        raw["purpose_detail"] = (raw["purpose_detail"] +
                                 f" Primary lateral damping {c_y:.3e} N.s/m and yaw damping "
                                 f"{c_yaw:.3e} N.m.s/rad are added to this synthetic case only; "
                                 "the inline baseline keeps zero.")
    raw["run"].update({
        "x_start_m": run_at_m,
        "seat_x_start_m": seat_at_m,
        "duration_s": duration_s,
        "output_step_s": 2.0e-4,
        "max_solver_step_s": 1.0e-4,
        "method": "BDF",
        "jacobian": "analytic",
    })
    raw["run"].pop("curve_radius_m", None)
    raw["run"].pop("curve_geometry", None)
    raw["run"].pop("align_to_track", None)
    if curvature_force:
        # The station table and `path` already carry the line, so nothing has to be *placed*.
        # What is still missing in that frame is the frame's own lateral acceleration: a frame
        # that translates with y(s) accelerates at v^2/R, so the vehicle inside it feels the
        # fictitious force +m v^2/R outward.  Declaring the radius without `curve_geometry`
        # is exactly how `evaluate` is asked for that term -- and, since the curvature gate on
        # the creep was removed, the +-v kappa b arc-length difference comes with it.
        raw["run"]["curve_radius_m"] = float(radius_m)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = "" if primary_lateral_damping is None else (
        f"_cy{primary_lateral_damping[0]:.0e}_cyaw{primary_lateral_damping[1]:.0e}")
    path = OUT / f"case_curved_R{radius_m:.0f}_t{tangent_m:.0f}{tag}.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


def frame_table(dynamics, q, v) -> None:
    force, contacts = dynamics.evaluate(0.0, q, v)
    total = 0.0
    for rail in dynamics.case.rails:
        response = contacts.get(rail.id)
        if response is None or response.geometry is None:
            print(f"    {rail.id:<14} no geometry")
            continue
        geometry = response.geometry
        total += response.normal_force_n
        print(f"    {rail.id:<14} N {response.normal_force_n:9.1f} "
              f"({response.normal_force_n / EVEN_SHARE_N:6.3f}x) "
              f"pen {geometry.penetration_m * 1e6:8.2f} um "
              f"lever_y {geometry.lever_y_m:+.5f} "
              f"n_y/n_z {geometry.normal_y / geometry.normal_z:+.4f} "
              f"slip_lat {response.slip_lateral_m_s:+.4f}")
    print(f"    sum N {total:.1f} N ({total / (EVEN_SHARE_N * 8):.3f}x weight)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=0.05)
    parser.add_argument("--radius", type=float, default=1100.0)
    parser.add_argument("--tangent", type=float, default=30.0)
    parser.add_argument("--step", type=float, default=0.1)
    parser.add_argument("--span", type=float, default=150.0)
    parser.add_argument("--run-at", type=float, default=30.0)
    parser.add_argument("--seat-at", type=float, default=30.0)
    parser.add_argument("--primary-damping", nargs=2, type=float, default=None,
                        metavar=("C_Y", "C_YAW"),
                        help="add primary lateral (N.s/m) and yaw (N.m.s/rad) damping to this "
                             "synthetic case only, to test whether the curve settles")
    parser.add_argument("--creep-scale", type=float, default=None,
                        help="DIAGNOSTIC: multiply f11 and f22 by this factor (10 gives the "
                             "physical 1e7 / 5e6 N); the frozen cases are untouched")
    parser.add_argument("--curvature-force", action="store_true",
                        help="add the frame's fictitious m v^2/R (curving load) to the station-table route")
    args = parser.parse_args(argv)

    path = build(radius_m=args.radius, tangent_m=args.tangent, step_m=args.step, span_m=args.span,
                 duration_s=args.duration, run_at_m=args.run_at, seat_at_m=args.seat_at,
                 curvature_force=args.curvature_force,
                 primary_lateral_damping=(None if args.primary_damping is None
                                          else tuple(args.primary_damping)),
                 creep_scale=args.creep_scale)
    case = load_vehicle_case(path)
    print(f"case {path.name}: R {args.radius:.0f} m, tangent {args.tangent:.0f} m, "
          f"{len(case.rails)} rails, path {len(case.path.stations_s_m)} points, "
          f"stations {len(case.rails[0].bodies[0].series.mileages())} per rail")
    print(f"  route at 40 m {float(y_route(40.0, args.tangent, args.radius)) * 1e3:+.2f} mm, "
          f"at 47.6 m {float(y_route(47.6, args.tangent, args.radius)) * 1e3:+.2f} mm")

    from velch.vehicle_solver import _seat
    dynamics = VehicleDynamics(case)
    velocity = np.zeros(dynamics.dimension)
    speed = float(case.vehicle.travel_speed_m_s)
    radius = float(case.vehicle.nominal_wheel_radius_m)
    for body in dynamics.topology.wheelsets():
        velocity[dynamics.topology.require(body.id, "spin")] = speed / radius
    seated, residual = _seat(case, dynamics, np.zeros(dynamics.dimension), velocity)
    print(f"  seat residual {residual:.3e} N")
    frame_table(dynamics, seated, velocity)

    result = simulate_vehicle(case)
    summary = result.summary
    failing = [gate for gate, ok in summary["gates"].items() if not ok]
    peaks = summary["peak_normal_force_n"]
    print(f"  run {args.duration} s -> {summary['result_status']}  "
          f"frames {result.positions.shape[0]}  gates "
          f"{sum(1 for ok in summary['gates'].values() if ok)}/{len(summary['gates'])} "
          f"failing {failing}")
    print(f"  max penetration {summary['max_penetration_m'] * 1e6:.2f} um")
    if isinstance(peaks, dict):
        print("  peaks " + ", ".join(f"{key} {float(value):.0f} "
                                     f"({float(value) / EVEN_SHARE_N:.2f}x)"
                                     for key, value in sorted(peaks.items())))

    # Last frame: is the vehicle being *steered* now, and does the load sit on the outer rail?
    last_contacts = result.contacts[-1]
    last_q = result.positions[-1]
    total_fy = 0.0
    total_n = 0.0
    left_n = right_n = 0.0
    for rail in case.rails:
        response = last_contacts.get(rail.id)
        if response is None or response.geometry is None:
            continue
        total_fy += float(response.wheel_force_y_n)
        total_n += float(response.normal_force_n)
        if str(rail.id).endswith("left"):
            left_n += float(response.normal_force_n)
        else:
            right_n += float(response.normal_force_n)
    demand = (sum(body.mass_kg for body in dynamics.topology.bodies)
              * speed * speed / args.radius)
    print(f"  last frame: sum Fy {total_fy:+.1f} N  (fictitious demand {demand:.1f} N, "
          f"{total_fy / demand:+.1%})  left {left_n:.0f} N / right {right_n:.0f} N  "
          f"transfer {left_n - right_n:+.0f} N")
    for rail in case.rails:
        response = last_contacts.get(rail.id)
        if response is None or response.geometry is None:
            print(f"    last {rail.id:<14} no geometry")
            continue
        geometry = response.geometry
        print(f"    last {rail.id:<14} N {response.normal_force_n:9.1f} "
              f"({response.normal_force_n / EVEN_SHARE_N:6.3f}x) "
              f"pen {geometry.penetration_m * 1e6:8.2f} um "
              f"lever_y {geometry.lever_y_m:+.5f} "
              f"Fy {response.wheel_force_y_n:+9.1f}")
    for body in dynamics.topology.wheelsets():
        y = dynamics.topology.require(body.id, "y")
        yaw = dynamics.topology.require(body.id, "yaw")
        print(f"    {body.id:<10} q[y] {last_q[y] * 1e3:+8.3f} mm   q[yaw] {last_q[yaw] * 1e6:+8.2f} urad")
    return 0


if __name__ == "__main__":
    sys.exit(main())
