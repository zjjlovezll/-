"""Does the seat balance the force it applies?  On the frame route it does not.

The station-table curve plus `curve_radius_m` (``--curvature-force``) is the one configuration where
the line and the frame's own acceleration coexist: the rails come from the station offsets and
``path``, while ``evaluate`` adds the fictitious ``m v^2/R`` because the vehicle rides an
accelerating frame.  So a steady state on that route satisfies

    F(q) + m v^2/R *(-1 in y) = 0

and the seat is supposed to return that q.  It does not: ``_static_vertical_equilibrium`` puts only
the vertical rows (plus wheelset yaw) among its unknowns, so the 21 842.4 N that ``evaluate`` adds
is never balanced by anything.  The run then starts with the *whole* curving load unbalanced, the
vehicle drifts outboard, creep builds up, and 0.34 s later the contact reads 78 % of the demand --
then overshoots to 151 % at 0.60 s and climbs onto the shoulder.

This script measures the difference directly, without touching the solver:

1. seat vertically (today's seat) and print the residual of the *lateral* rows at that state;
2. re-solve with y, roll and yaw among the unknowns and print the same rows, the eight patches and
   ``sum Fy`` against the demand.

If (2) converges with eight wheels inside the band, then the curve failure is a *seat* defect, not a
contact-law boundary: the physics admits a steady curving state, and the solver was standing the
vehicle at a point where the equations it had written down were not satisfied.

Run:  python -X utf8 scripts/s43_running_equilibrium.py [--radius 1100] [--speed-kmh 80]
                                                        [--creep-scale 1]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parent / "scratch" / "s43"
EVEN_SHARE_N = 59_662.0


def builder():
    """Load `s32_curved_station_table` without making the scripts directory a package."""

    spec = importlib.util.spec_from_file_location(
        "s32_curved_station_table", ROOT / "scripts" / "s32_curved_station_table.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_case(*, radius_m: float, speed_kmh: float, run_at_m: float, seat_at_m: float,
               creep_scale: float, duration_s: float) -> Path:
    s32 = builder()
    s32.SPEED_KMH = speed_kmh
    base = s32.build(radius_m=radius_m, tangent_m=seat_at_m, step_m=0.1, span_m=180.0,
                     duration_s=duration_s, run_at_m=run_at_m, seat_at_m=seat_at_m,
                     curvature_force=True,
                     creep_scale=None if creep_scale == 1.0 else creep_scale)
    raw = json.loads(Path(base).read_text(encoding="utf-8"))
    raw["case_id"] = (f"frame_equilibrium_R{radius_m:.0f}_t{seat_at_m:.0f}"
                      f"{'' if creep_scale == 1.0 else f'_creep{creep_scale:g}'}")
    target = SCRATCH / f"{raw['case_id']}.json"
    SCRATCH.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return target


def lateral_rows(dynamics, q: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, list[int]]:
    """The lateral-family rows of the force vector, and the coordinates they belong to."""

    topology = dynamics.topology
    indices: list[int] = []
    for body in topology.bodies:
        for axis in ("y", "roll", "yaw"):
            if axis in body.dof:
                indices.append(topology.require(body.id, axis))
    force, _ = dynamics.evaluate(0.0, q, v)
    return force[np.asarray(indices, dtype=int)], indices


def solve_frame_equilibrium(case, dynamics, q: np.ndarray, v: np.ndarray, *,
                            include_lateral: bool) -> tuple[np.ndarray, float, float, int]:
    """Newton on ``F(q) = 0``; ``include_lateral`` decides whether y/roll/yaw are unknowns."""

    topology = dynamics.topology
    indices = [topology.require(body.id, "z") for body in topology.bodies if "z" in body.dof]
    if include_lateral:
        for body in topology.bodies:
            for axis in ("y", "roll", "yaw"):
                if axis in body.dof:
                    indices.append(topology.require(body.id, axis))
    indices_array = np.asarray(indices, dtype=int)
    hits = 0

    def residual(values: np.ndarray) -> np.ndarray:
        nonlocal hits
        trial = q.copy()
        trial[indices_array] = values
        try:
            force, _ = dynamics.evaluate(0.0, trial, v)
        except Exception:
            hits += 1
            return np.full(len(indices_array), 1.0)
        return force[indices_array] / 1e5

    seeds = [q[indices_array].copy()]
    if include_lateral:
        for lateral in (-3.0e-3, -1.5e-3, 1.5e-3, 3.0e-3):
            seeded = q.copy()
            for body in topology.wheelsets():
                seeded[topology.require(body.id, "y")] += lateral
            seeds.append(seeded[indices_array].copy())
        for attack in (-4.0e-3, -2.0e-3, 2.0e-3, 4.0e-3):
            seeded = q.copy()
            for body in topology.wheelsets():
                seeded[topology.require(body.id, "yaw")] += attack
            seeds.append(seeded[indices_array].copy())
    best: tuple[float, np.ndarray] | None = None
    last = ""
    for index, seed in enumerate(seeds):
        solved = least_squares(residual, seed, method="trf", xtol=1e-12, ftol=1e-12, gtol=1e-12,
                               max_nfev=1500)
        error_n = float(np.max(np.abs(residual(solved.x))) * 1e5)
        last = str(solved.message)
        print(f"    seed {index:2d}: |r|max {error_n:12.4e} N  nfev {solved.nfev:5d}  "
              f"{solved.message[:58]}")
        if np.all(np.isfinite(solved.x)) and (best is None or error_n < best[0]):
            best = (error_n, solved.x.copy())
        if error_n < 0.1:
            break
    assert best is not None, last
    error_n, values = best
    settled = q.copy()
    settled[indices_array] = values
    jacobian = np.zeros((len(indices_array), len(indices_array)))
    step = 1.0e-6
    for column in range(len(indices_array)):
        delta = np.zeros(len(indices_array))
        delta[column] = step
        jacobian[:, column] = (residual(values + delta) - residual(values - delta)) / (2.0 * step)
    singular = np.linalg.svd(jacobian, compute_uv=False)
    cond = float(singular[0] / singular[-1]) if singular[-1] > 0 else float("inf")
    return settled, error_n, cond, hits


def capability_sweep(case, dynamics, seated: np.ndarray, v: np.ndarray, *,
                     demand_n: float, offsets_mm, attacks_mrad=(0.0,)) -> list[dict]:
    """How much lateral force can the contact carry, with the wheels still on the tread?

    The lateral rows are *not* solved here.  A prescribed lateral offset (and attack angle) is put
    on every wheelset, the vertical rows are re-seated at that geometry, and the contact's own
    net lateral force is read.  That separates "the contact cannot deliver 21.8 kN on the tread"
    from "the trajectory has not settled yet", which no single run can do.
    """

    from velch.vehicle_solver import _load_per_wheel

    topology = dynamics.topology
    rows: list[dict] = []
    for attack in attacks_mrad:
        for offset in offsets_mm:
            trial = seated.copy()
            for body in topology.wheelsets():
                if "y" in body.dof:
                    trial[topology.require(body.id, "y")] += float(offset) * 1e-3
                if "yaw" in body.dof:
                    trial[topology.require(body.id, "yaw")] += float(attack) * 1e-3
            settled, error_n, _, _ = solve_frame_equilibrium(case, dynamics, trial, v,
                                                             include_lateral=False)
            force, contacts = dynamics.evaluate(0.0, settled, v)
            loads = {rail.id: float(contacts[rail.id].normal_force_n)
                     for rail in case.rails if contacts.get(rail.id) is not None}
            per_wheel = _load_per_wheel(case.rails, [loads.get(rail.id, 0.0) for rail in case.rails])
            ratios = [value / EVEN_SHARE_N for value in per_wheel.values()]
            total_fy = sum(float(contacts[rail.id].wheel_force_y_n) for rail in case.rails
                           if contacts.get(rail.id) is not None)
            penetration = max((float(contacts[rail.id].geometry.penetration_m)
                               for rail in case.rails
                               if contacts.get(rail.id) is not None
                               and contacts[rail.id].geometry is not None), default=0.0)
            inside = bool(ratios) and min(ratios) >= 0.625 and max(ratios) <= 1.6
            print(f"    attack {attack:+5.1f} mrad  offset {offset:+5.2f} mm -> "
                  f"sum Fy {total_fy:+9.1f} N ({total_fy / demand_n * 100:+6.1f} %)  "
                  f"|r|z {error_n:.2e} N  ratio {min(ratios):.3f}..{max(ratios):.3f} "
                  f"{'in band' if inside else 'OUT'}  max pen {penetration * 1e6:7.2f} um")
            rows.append({"attack_mrad": float(attack), "offset_mm": float(offset),
                         "sum_fy_n": total_fy, "ratio_min": min(ratios),
                         "ratio_max": max(ratios), "in_band": inside,
                         "max_penetration_m": penetration, "vertical_residual_n": error_n})
    return rows


def table(case, dynamics, q: np.ndarray, v: np.ndarray, *, demand_n: float) -> dict:
    force, contacts = dynamics.evaluate(0.0, q, v)
    from velch.vehicle_solver import _load_per_wheel

    total_n = 0.0
    total_fy = 0.0
    rail_loads: list[float] = []
    for rail in case.rails:
        response = contacts.get(rail.id)
        rail_loads.append(0.0 if response is None else float(response.normal_force_n))
        if response is None or response.geometry is None:
            print(f"    {rail.id:<14} no geometry")
            continue
        geometry = response.geometry
        total_n += response.normal_force_n
        total_fy += response.wheel_force_y_n
        print(f"    {rail.id:<14} N {response.normal_force_n:9.1f} "
              f"({response.normal_force_n / EVEN_SHARE_N:6.3f}x) "
              f"pen {geometry.penetration_m * 1e6:8.2f} um "
              f"lever_y {geometry.lever_y_m:+.5f} "
              f"n_y/n_z {geometry.normal_y / geometry.normal_z:+.4f} "
              f"slip_lat {response.slip_lateral_m_s:+.5f} Fy {response.wheel_force_y_n:+9.1f}")
    # Group by *wheel*, not by rail: a turnout declares several surfaces per side and a synthetic
    # table can carry the same wheel on one rail only, so grouping by (axle, side) folded two rails
    # into one wheel and reported "4/8 loaded, 2.001x" on a perfectly even seat -- my own mistake,
    # found by reading the numbers against the per-rail loads.
    per_wheel = _load_per_wheel(case.rails, rail_loads)
    ratios = [value / EVEN_SHARE_N for value in per_wheel.values()]
    print(f"    sum N {total_n:9.1f} N ({total_n / (EVEN_SHARE_N * 8):.3f}x weight)   "
          f"sum Fy {total_fy:+9.1f} N ({total_fy / demand_n * 100:+.1f} % of the "
          f"{demand_n:.1f} N demand)")
    if ratios:
        print(f"    wheels loaded {len(ratios)}/{2 * len(dynamics.topology.wheelsets())}, "
              f"ratios {min(ratios):.3f}..{max(ratios):.3f}")
    return {"sum_normal_n": total_n, "sum_fy_n": total_fy, "ratios": ratios,
            "force": force}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radius", type=float, default=1100.0)
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    parser.add_argument("--run-at", type=float, default=30.0)
    parser.add_argument("--seat-at", type=float, default=30.0)
    parser.add_argument("--creep-scale", type=float, default=1.0)
    parser.add_argument("--duration", type=float, default=0.02)
    parser.add_argument("--run", type=float, default=0.0,
                        help="integrate this long from the solved state (needs --duration >= it)")
    parser.add_argument("--capability", action="store_true",
                        help="sweep a prescribed lateral offset and attack on every wheelset, "
                             "re-seat the vertical rows at that geometry, and report the lateral "
                             "force the seated contact can actually carry")
    args = parser.parse_args(argv)

    path = build_case(radius_m=args.radius, speed_kmh=args.speed_kmh, run_at_m=args.run_at,
                      seat_at_m=args.seat_at, creep_scale=args.creep_scale,
                      duration_s=max(args.duration, args.run + 0.01))
    case = load_vehicle_case(path)
    dynamics = VehicleDynamics(case)
    speed = float(case.vehicle.travel_speed_m_s)
    mass = sum(body.mass_kg for body in dynamics.topology.bodies)
    demand_n = mass * speed * speed / args.radius
    print(f"case {path.name}: R {args.radius:.0f} m, {args.speed_kmh:.1f} km/h ({speed:.4f} m/s), "
          f"mass {mass:.1f} kg, frame force m v^2/R {demand_n:.1f} N")

    zeros = np.zeros(dynamics.dimension)
    velocity = np.zeros(dynamics.dimension)
    radius_wheel = float(case.vehicle.nominal_wheel_radius_m)
    for body in dynamics.topology.wheelsets():
        velocity[dynamics.topology.require(body.id, "spin")] = speed / radius_wheel
    seated, seat_residual = _seat(case, dynamics, zeros, velocity)
    print(f"\n1) today's seat (vertical rows only): residual {seat_residual:.3e} N")
    table(case, dynamics, seated, velocity, demand_n=demand_n)
    lateral, _ = lateral_rows(dynamics, seated, velocity)
    print(f"   the lateral rows it does not solve: {np.array2string(lateral / 1e5, precision=4)} "
          f"(x1e5 N)  |max| {float(np.max(np.abs(lateral))):.1f} N")

    print("\n2) same equations, with y/roll/yaw among the unknowns:")
    settled, error_n, cond, hits = solve_frame_equilibrium(case, dynamics, seated, velocity,
                                                           include_lateral=True)
    outcome = table(case, dynamics, settled, velocity, demand_n=demand_n)
    wheel_y = [float(settled[dynamics.topology.require(body.id, "y")]) * 1e3
               for body in dynamics.topology.wheelsets() if "y" in body.dof]
    wheel_yaw = [float(settled[dynamics.topology.require(body.id, "yaw")]) * 1e3
                 for body in dynamics.topology.wheelsets() if "yaw" in body.dof]
    print(f"   |r|max {error_n:.3e} N, cond {cond:.3e}, barrier hits {hits}")
    print(f"   wheelset y {[round(value, 3) for value in wheel_y]} mm, "
          f"yaw {[round(value, 3) for value in wheel_yaw]} mrad")
    ratios = outcome["ratios"]
    inside = bool(ratios) and min(ratios) >= 0.625 and max(ratios) <= 1.6
    verdict = ("BALANCED" if error_n < 0.1 and inside else
               "CONVERGED OUTSIDE THE BAND" if error_n < 0.1 else "NOT FOUND")
    print(f"   VERDICT {verdict}: |r|max {error_n:.3e} N, "
          f"wheels inside the band {all(0.625 <= r <= 1.6 for r in ratios)}")

    capability: list[dict] = []
    if args.capability:
        print("\n3) lateral force the seated contact can carry "
              "(offset / attack prescribed, vertical rows re-seated at each point):")
        capability = capability_sweep(case, dynamics, seated, velocity, demand_n=demand_n,
                                      offsets_mm=[-4.0 + 0.5 * index for index in range(17)],
                                      attacks_mrad=(0.0, 1.0, 2.0))
        in_band = [row for row in capability if row["in_band"]]
        best = max(in_band, key=lambda row: abs(row["sum_fy_n"]), default=None)
        if best is None:
            print("   no in-band state at all: the contact cannot carry the curve on the tread")
        else:
            print(f"   best in-band: attack {best['attack_mrad']:+.1f} mrad offset "
                  f"{best['offset_mm']:+.2f} mm -> |sum Fy| {abs(best['sum_fy_n']):.1f} N = "
                  f"{abs(best['sum_fy_n']) / demand_n * 100:.1f} % of the {demand_n:.1f} N demand, "
                  f"max pen {best['max_penetration_m'] * 1e6:.2f} um")
            if abs(best["sum_fy_n"]) < demand_n:
                print(f"   SHORT by {demand_n - abs(best['sum_fy_n']):.1f} N: on the tread this "
                      f"contact cannot hold the curve, whatever the transient does")

    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / f"{path.stem}_result.json").write_text(json.dumps({
        "case": path.name, "radius_m": args.radius, "speed_kmh": args.speed_kmh,
        "creep_scale": args.creep_scale, "demand_n": demand_n,
        "seat_residual_n": seat_residual,
        "unbalanced_lateral_rows_n": [float(value) for value in lateral],
        "frame_residual_n": error_n, "cond": cond, "barrier_hits": hits,
        "sum_normal_n": outcome["sum_normal_n"], "sum_fy_n": outcome["sum_fy_n"],
        "wheel_ratios": ratios, "wheel_y_mm": wheel_y, "wheel_yaw_mrad": wheel_yaw,
        "verdict": verdict, "capability": capability,
    }, indent=1), encoding="utf-8")
    return 0 if verdict == "BALANCED" else 2


if __name__ == "__main__":
    sys.exit(main())
