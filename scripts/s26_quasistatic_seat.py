"""Is a curved turnout seatable when the wheelset is *rolling* rather than standing?

The vertical seat deliberately leaves y/roll/yaw out.  The recorded reason is a rank deficiency:
at zero speed every creep force is zero, a crown contact carries no lateral component, so the
lateral rows have no solution (cond 3.76e12, smallest singular value 2.7e-11, every seed stuck at a
stationary 240 kN).  The physical reading is Elkins & Gostling (VSD 1977): a curve is *entered*, the
lateral state is a running equilibrium.

That leaves one experiment this repository has never run: keep the geometry as it is, but give the
wheelsets their rolling spin ``omega = v / r`` and the yaw term its speed ``travel * psi``, then ask
for a *quasi-static* equilibrium over {y, z, roll, yaw}.  ``contact.py`` already carries both terms
(``creep_attack_velocity_m_s = travel * yaw``, ``slip_x = travel + omega * lever_z - kappa *
travel * lever_y``), so no physics has to be added -- only the seat's velocity field and unknowns.

Run:  python -X utf8 scripts/s26_quasistatic_seat.py
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import (
    SimulationFailure,
    VehicleDynamics,
    _align_to_track_frame,
    _load_per_wheel,
)

SPEED_KMH = 80.0
SEAT_AT_M = 69.0          # on the diverging route, past the 50.578 m tangent
DURATION_S = 0.01
LOW, HIGH = 0.625, 1.6


def build(start_m: float):
    raw = json.loads((data_root.case_dir() / "case_diverging_R1100.json").read_text(encoding="utf-8"))
    raw["run"].update({
        "x_start_m": start_m,
        "duration_s": DURATION_S,
        "output_step_s": DURATION_S,
        # The curve lives in the station table, not in curve_radius_m.  curve_geometry is what
        # _placement_enabled reads, so it is the switch that lets _align_to_track_frame act;
        # _curve_placement returns None without a radius, so nothing is counted twice.
        "curve_geometry": True,
        "align_to_track": True,
    })
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw.pop("initial_state", None)
    # Inside the workspace: F:\velch_tmp is outside the write sandbox.
    path = Path(__file__).resolve().parents[2] / "scratch" / "seat26" / f"turnout_{start_m:g}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return load_vehicle_case(path)


def rolling_velocity(case, dynamics, q):
    """Spin every wheelset at ``travel / r`` so the creep law sees pure rolling, not a locked wheel.

    Left at zero, ``slip_x = travel`` = 22 m/s and the creep force is saturated: the seat would be
    solving a sliding contact and every residual would be ~friction, not equilibrium.
    """

    velocity = np.zeros(dynamics.dimension)
    topology = dynamics.topology
    speed = abs(float(case.vehicle.travel_speed_m_s))
    radius = float(case.vehicle.nominal_wheel_radius_m)
    sign = 1.0 if float(case.vehicle.travel_speed_m_s) >= 0.0 else -1.0
    for body in topology.wheelsets():
        velocity[topology.require(body.id, "spin")] = sign * speed / radius
    return velocity


def rows_for(dynamics, names=("y", "z", "roll", "yaw")) -> list[int]:
    topology = dynamics.topology
    rows: list[int] = []
    for body in topology.bodies:
        for name in names:
            if name in body.dof:
                rows.append(topology.require(body.id, name))
    if dynamics.case.track_kind == "local_compliant":
        rows += [topology.body_dimension + 2 * i + 1 for i in range(len(dynamics.case.rails))]
    return sorted(set(rows))


def labels_for(dynamics, rows) -> dict[int, str]:
    topology = dynamics.topology
    named: dict[int, str] = {}
    for body in topology.bodies:
        for name in body.dof:
            try:
                named[topology.require(body.id, name)] = f"{body.id}.{name}"
            except Exception:  # pragma: no cover - defence only
                pass
    for i, rail in enumerate(dynamics.case.rails):
        named[topology.body_dimension + 2 * i + 1] = f"{rail.id}.track_z"
    return {row: named.get(row, f"row{row}") for row in rows}


def aligned(case, dynamics, q, mode: str):
    """``_align_to_track_frame`` but able to keep only part of it.

    The yaw coordinate carries two meanings at once and this is the experiment that says so.

    * ``_align_to_track_frame`` writes ``yaw = arctan(dy/ds)``, the body's **absolute heading**.
    * ``contact.py`` turns the same coordinate into a creep **angle of attack**:
      ``creep_attack_velocity_m_s = travel * q[yaw]``.

    On a curve those differ by the track's own tangent angle.  At R = 1100 m and
    ``x_start = 69 m`` the tangent is 0.0158 rad, so an aligned wheelset is told it attacks the rail
    at 0.9 deg: ``travel * yaw = 0.352 m/s`` of lateral creep, i.e. a saturated lateral force of
    order 150 kN per contact, pointing sideways, on every wheel.  That is not guidance, it is a
    spurious force -- and it is a candidate explanation for every "the geometric curve cannot seat"
    reading in this repository.
    """

    shifted = _align_to_track_frame(case, dynamics, q)
    topology = dynamics.topology
    if mode == "full":
        return shifted
    result = np.array(q, dtype=float, copy=True)
    for body in topology.bodies:
        if "y" in body.dof:
            result[topology.require(body.id, "y")] = shifted[topology.require(body.id, "y")]
        if "yaw" in body.dof and mode == "yaw":
            result[topology.require(body.id, "yaw")] = shifted[topology.require(body.id, "yaw")]
    return result


def main() -> int:
    modes = sys.argv[1:] or ["none", "shift", "yaw", "full"]
    for mode in modes:
        print(f"\n=== alignment: {mode} ===")
        run_one(mode)
    return 0


def run_one(mode: str) -> None:
    case = build(SEAT_AT_M)
    dynamics = VehicleDynamics(case)
    q = np.zeros(dynamics.dimension)
    velocity = rolling_velocity(case, dynamics, q)
    q = aligned(case, dynamics, q, mode)

    topology = dynamics.topology
    print(f"coordinates          : {dynamics.dimension}  (track kind {case.track_kind})")
    print(f"travel speed         : {case.vehicle.travel_speed_m_s:.4f} m/s")
    print(f"wheelset spin        : {velocity[topology.require(topology.wheelsets()[0].id, 'spin')]:.4f} rad/s")
    if "yaw" in topology.wheelsets()[0].dof:
        print(f"front wheelset yaw   : {q[topology.require(topology.wheelsets()[0].id, 'yaw')]:+.6f} rad "
              f"-> creep attack velocity "
              f"{case.vehicle.travel_speed_m_s * q[topology.require(topology.wheelsets()[0].id, 'yaw')]:+.4f} m/s"
              f" (a slip ratio of "
              f"{q[topology.require(topology.wheelsets()[0].id, 'yaw')]:+.4f})")

    indices = rows_for(dynamics)
    labels = labels_for(dynamics, indices)
    print(f"quasi-static unknowns: {len(indices)}")

    def loads_of(state):
        _, contacts = dynamics.evaluate(0.0, state, velocity)
        loads = [float(contacts[rail.id].normal_force_n) for rail in case.rails]
        return loads

    failures = [0]

    def residual(values, base):
        trial = base.copy()
        trial[indices] = values
        try:
            force, _ = dynamics.evaluate(0.0, trial, velocity)
        except SimulationFailure:
            failures[0] += 1
            return np.full(len(indices), 1.0)
        return force[indices] / 1e5

    seeds = [("aligned", q[indices].copy())]
    for drop in (2.0e-3, 1.0e-3):
        seeded = q.copy()
        for body in topology.wheelsets():
            seeded[topology.require(body.id, "z")] -= drop
        for body in topology.bogies():
            seeded[topology.require(body.id, "z")] -= drop
        seeds.append((f"drop {drop * 1e3:g} mm", seeded[indices].copy()))

    started = time.time()
    best = None
    for name, seed in seeds:
        base = q.copy()
        base[indices] = seed
        solved = least_squares(lambda x, b=base: residual(x, b), seed, method="trf",
                               xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=600)
        worst = residual(solved.x, base)
        error_n = float(np.max(np.abs(worst)) * 1e5)
        print(f"seed {name:<12s} -> |r|max {error_n:10.4e} N   {solved.message}")
        order = np.argsort(-np.abs(worst))[:6]
        for row in order:
            print(f"      {labels[indices[row]]:<22s} {worst[row] * 1e5:12.1f} N")
        if best is None or error_n < best[0]:
            best = (error_n, solved, base)
    elapsed = time.time() - started
    error_n, solved, base = best
    print(f"elapsed              : {elapsed:.1f} s   (guard hits {failures[0]})")
    print(f"best worst residual  : {error_n:.4e} N")

    with np.errstate(all="ignore"):
        singular = np.linalg.svd(solved.jac, compute_uv=False)
        cond = float(singular[0] / singular[-1]) if singular[-1] > 0 else math.inf
        print(f"condition number     : {cond:.3e}  (sigma_max {singular[0]:.3e}, "
              f"sigma_min {singular[-1]:.3e})")

    trial = base.copy()
    trial[indices] = solved.x
    try:
        loads = loads_of(trial)
    except SimulationFailure as error:
        print(f"evaluate after solve : raised {error}")
        return 1
    per_wheel = _load_per_wheel(case.rails, loads)
    weight = case.vehicle.gravity_m_s2 * sum(b.mass_kg for b in topology.bodies)
    share = weight / max(len(per_wheel), 1)
    active = {key: value for key, value in per_wheel.items() if value > 0.0}
    print(f"even share           : {share:.1f} N")
    print(f"wheels carrying load : {len(active)} of {len(per_wheel)}")
    for (axle, side), value in sorted(per_wheel.items()):
        print(f"  axle{axle + 1}_{side:<5s} {value:10.1f} N  {value / share:6.3f}x")
    if active:
        ratios = [value / share for value in active.values()]
        print(f"ratio range          : {min(ratios):.3f} .. {max(ratios):.3f} "
              f"({'inside' if min(ratios) >= LOW and max(ratios) <= HIGH else 'OUTSIDE'} "
              f"{LOW}..{HIGH})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
