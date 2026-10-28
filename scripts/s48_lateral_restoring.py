"""What holds the vehicle sideways?  Measure the restoring stiffness of the seated curve.

Round 205 left one specific hole in the account of the curve.  With the cant in the frame the
required contact lateral force falls from 21 842.4 N to 2 662 N and the eight wheels sit inside
[0.625, 1.6] for 0.60 s -- but at 1.0 s the load transfer has grown to +152 849 N and ``axle1_left``
reaches 1.99x.  The eigenvalue sweep of that round said why: once the yaw damping is present the
largest real part is a **0.00 Hz** mode, i.e. the vehicle body has no lateral *restoring* term and a
force imbalance just walks it sideways until the contact nonlinearity stops it -- by which time the
loads are long out of band.

So the question this script answers is a one-line one:

    how many newtons of lateral force does 1 m of lateral displacement produce?

and it answers it on the seated state, with the vertical rows re-seated at each offset so that the
weight stays at 1.000x and only the lateral response is being measured.  Three numbers come out:

* ``k_force``  = -d(sum Fy)/dy      N/m  -- the restoring the *contact model* offers;
* ``k_yaw``    = -d(sum M_yaw)/dy   N.m/m -- the restoring it offers as a yaw moment;
* ``lam_eff``  = d(r_L - r_R)/dy / 2      -- the effective conicity the *profiles* carry, and with it
  Wickens' gravitational stiffness ``k_grav = W/4 * lam / r`` N/m, which is what a real wheelset
  gets its lateral location from.

Pre-registered reading (fixed before the run, in this docstring, so the numbers cannot pick it):

* ``RESTORING PRESENT``  -- ``k_force`` lies in [0.5, 2.0] * ``k_grav``: the contact model carries the
  same lateral location a real wheelset does, and the 1.0 s walk is a damping/transient problem.
* ``RESTORING BLIND``    -- ``0.0 <= k_force < 0.2 * k_grav``: the model has essentially no static
  lateral restoring, which is exactly what the 0.00 Hz mode looked like.  Register it as a defect:
  the seat cannot hold a curve because nothing in the model pulls the vehicle back.
* ``RESTORING INVERTED`` -- ``k_force < 0``: the response pushes the vehicle further out; that is a
  sign error somewhere and outranks both of the above.

Run:

    python -X utf8 scripts/s48_lateral_restoring.py [--cant 0.060] [--creep-kalker] [--span 2.0]
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
SCRATCH = ROOT.parent / "scratch" / "s48"

SPEED_KMH = 80.0
RADIUS_M = 1100.0
CANT_M = 0.060
RUN_AT_M = 30.0
SEAT_AT_M = 30.0
EVEN_SHARE_N = 59_662.0


def builder():
    path = ROOT / "scripts" / "s32_curved_station_table.py"
    spec = importlib.util.spec_from_file_location("s32_curved_station_table", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_case(*, cant_m: float, creep_kalker: bool, duration_s: float) -> Path:
    s32 = builder()
    s32.SPEED_KMH = SPEED_KMH
    base = s32.build(radius_m=RADIUS_M, tangent_m=SEAT_AT_M, step_m=0.1, span_m=180.0,
                     duration_s=duration_s, run_at_m=RUN_AT_M, seat_at_m=SEAT_AT_M,
                     curvature_force=True, cant_m=cant_m, creep_kalker=creep_kalker)
    raw = json.loads(Path(base).read_text(encoding="utf-8"))
    raw["case_id"] = (f"lateral_restoring_R{RADIUS_M:.0f}_c{cant_m * 1e3:.0f}mm"
                      f"{'_kalker' if creep_kalker else ''}")
    target = SCRATCH / f"{raw['case_id']}.json"
    SCRATCH.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return target


def rolling_velocity(dynamics: VehicleDynamics, case, speed_m_s: float) -> np.ndarray:
    """Every wheelset spinning at exactly v/r, so the creep reads a rolling contact."""

    topology = dynamics.topology
    radius = float(case.vehicle.nominal_wheel_radius_m)
    velocity = np.zeros(dynamics.dimension)
    for body in topology.wheelsets():
        velocity[topology.require(body.id, "spin")] = speed_m_s / radius
    return velocity


def reseat_vertical(dynamics: VehicleDynamics, q: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, float]:
    """Solve only the vertical rows, so the weight stays at 1.000x and only y moved."""

    topology = dynamics.topology
    indices = np.asarray([topology.require(body.id, "z")
                          for body in topology.bodies if "z" in body.dof], dtype=int)

    def residual(values: np.ndarray) -> np.ndarray:
        trial = q.copy()
        trial[indices] = values
        try:
            force, _ = dynamics.evaluate(0.0, trial, v)
        except Exception:
            return np.full(len(indices), 1.0)
        return force[indices] / 1e5

    solved = least_squares(residual, q[indices].copy(), method="trf",
                           xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=1500)
    settled = q.copy()
    settled[indices] = solved.x
    return settled, float(np.max(np.abs(residual(solved.x))) * 1e5)


def probe(case, dynamics: VehicleDynamics, q: np.ndarray, v: np.ndarray) -> dict:
    """One evaluation: per-rail force and geometry, summed lateral force, per-wheelset yaw moment."""

    _, contacts = dynamics.evaluate(0.0, q, v)
    total_n = 0.0
    total_fy = 0.0
    sum_left = 0.0
    sum_right = 0.0
    yaw_moment: dict[str, float] = {}
    radius: dict[tuple[str, str], float] = {}
    for rail in case.rails:
        response = contacts.get(rail.id)
        if response is None or response.geometry is None:
            continue
        geometry = response.geometry
        total_n += response.normal_force_n
        total_fy += response.wheel_force_y_n
        if "_left" in rail.id:
            sum_left += response.normal_force_n
        else:
            sum_right += response.normal_force_n
        axle, _, side = rail.id.partition("_")
        wheelset = "wheelset" + axle.removeprefix("axle")
        # The yaw moment about the wheelset centre from the two longitudinal creep forces.
        yaw_moment[wheelset] = (yaw_moment.get(wheelset, 0.0)
                                - geometry.lever_y_m * response.longitudinal_force_n)
        # lever_z is the contact height below the wheelset centre, i.e. minus the rolling radius.
        radius[(axle, side)] = -geometry.lever_z_m
    return {"sum_normal_n": total_n, "sum_fy_n": total_fy,
            "transfer_n": sum_left - sum_right,
            "yaw_moment_nm": sum(yaw_moment.values()),
            "radius": radius, "contacts": len(radius)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cant", type=float, default=CANT_M)
    parser.add_argument("--creep-kalker", action="store_true")
    parser.add_argument("--span", type=float, default=2.0, help="lateral sweep half width, mm")
    parser.add_argument("--step", type=float, default=0.5, help="lateral sweep step, mm")
    args = parser.parse_args(argv)

    speed_m_s = SPEED_KMH / 3.6
    case_path = build_case(cant_m=args.cant, creep_kalker=args.creep_kalker, duration_s=0.001)
    print(f"case            {case_path}")
    case = load_vehicle_case(case_path)
    dynamics = VehicleDynamics(case)
    topology = dynamics.topology
    v = rolling_velocity(dynamics, case, speed_m_s)

    weight = sum(body.mass_kg for body in topology.bodies) * 9.81
    print(f"coordinates     {dynamics.dimension}")
    print(f"speed           {speed_m_s:.4f} m/s ({SPEED_KMH:.1f} km/h)   spin "
          f"{speed_m_s / case.vehicle.nominal_wheel_radius_m:.4f} rad/s")
    print(f"weight          {weight:.1f} N   even share {EVEN_SHARE_N:.1f} N/wheel")

    seated, residual = _seat(case, dynamics, np.zeros(dynamics.dimension), v)
    print(f"seated          residual {residual:.3e} N")

    lateral = [topology.require(body.id, "y") for body in topology.bodies if "y" in body.dof]
    offsets = np.arange(-args.span, args.span + 0.25 * args.step, args.step) * 1e-3

    rows: list[dict] = []
    state = seated
    for offset in offsets:
        q = state.copy()
        for index in lateral:
            q[index] = seated[index] + float(offset)
        q, seat_residual = reseat_vertical(dynamics, q, v)
        state = q
        measured = probe(case, dynamics, q, v)
        radii = measured.pop("radius")
        conicity: list[float] = []
        for axle in sorted({key[0] for key in radii}):
            left = radii.get((axle, "left"))
            right = radii.get((axle, "right"))
            if left is None or right is None:
                continue
            conicity.append(left - right)
        measured["radius_difference_m"] = float(np.mean(conicity)) if conicity else float("nan")
        measured["offset_m"] = float(offset)
        measured["seat_residual_n"] = seat_residual
        rows.append(measured)
        print(f"  offset {offset * 1e3:+5.2f} mm  seat {seat_residual:8.2e} N  "
              f"sum N {measured['sum_normal_n']:9.1f}  sum Fy {measured['sum_fy_n']:+9.1f}  "
              f"transfer {measured['transfer_n']:+9.1f}  M_yaw {measured['yaw_moment_nm']:+9.1f}  "
              f"rL-rR {measured['radius_difference_m'] * 1e6:+7.1f} um")

    def slope(key: str) -> float:
        values = np.array([row[key] for row in rows])
        return float(np.polyfit(offsets, values, 1)[0])

    k_force = -slope("sum_fy_n")
    k_yaw = -slope("yaw_moment_nm")
    k_transfer = -slope("transfer_n")
    # Physical conicity: shifting the wheelset towards +y must *increase* the radius on that side,
    # so `lambda = 1/2 d(r_right - r_left)/dy`, which is minus half the slope recorded above (that
    # column stores r_left - r_right).  Measured here at -0.0478 m/m, i.e. lambda = 0.0239 -- a
    # 1:42 tread, which is what these profiles carry.
    lam_eff = -0.5 * slope("radius_difference_m")
    radius = float(case.vehicle.nominal_wheel_radius_m)
    wheelsets = len(list(topology.wheelsets()))
    k_grav = (weight / wheelsets) * lam_eff / radius if lam_eff > 0.0 else float("nan")

    print()
    print(f"k_force    {k_force / 1e3:+9.2f} kN/m    restoring lateral force per metre of shift")
    print(f"k_yaw      {k_yaw / 1e3:+9.2f} kN.m/m  restoring yaw moment per metre of shift")
    print(f"k_transfer {k_transfer / 1e3:+9.2f} kN/m    left-minus-right load per metre of shift")
    print(f"lam_eff    {lam_eff:+.5f}          effective conicity from the profiles")
    print(f"k_grav     {k_grav / 1e3:+9.2f} kN/m    Wickens W/n * lam / r per wheelset")

    if not np.isfinite(k_grav) or k_grav <= 0.0:
        verdict = "NO CONICITY: the profiles carry no rolling-radius difference, so k_grav is undefined"
    elif k_force < 0.0:
        verdict = "RESTORING INVERTED: the response pushes the vehicle further out"
    elif k_force < 0.2 * k_grav:
        verdict = "RESTORING BLIND: the model has essentially no static lateral restoring"
    elif k_force <= 2.0 * k_grav:
        verdict = "RESTORING PRESENT: same order as a real wheelset's gravitational stiffness"
    else:
        verdict = "RESTORING STIFF: more than twice the gravitational stiffness"
    print(f"VERDICT {verdict}")

    SCRATCH.mkdir(parents=True, exist_ok=True)
    out = SCRATCH / (f"restoring_c{args.cant * 1e3:.0f}mm{'_kalker' if args.creep_kalker else ''}.json")
    out.write_text(json.dumps({
        "speed_kmh": SPEED_KMH, "radius_m": RADIUS_M, "cant_m": args.cant,
        "creep_kalker": args.creep_kalker, "weight_n": weight, "wheelsets": wheelsets,
        "rows": rows, "k_force_n_per_m": k_force, "k_yaw_nm_per_m": k_yaw,
        "k_transfer_n_per_m": k_transfer, "lam_eff": lam_eff, "k_grav_n_per_m": k_grav,
        "verdict": verdict,
    }, indent=1), encoding="utf-8")
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
