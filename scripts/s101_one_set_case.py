"""Build the "one set" case: the complete car, flexible wheelsets, compliant track, real turnout.

The goal asks for one model that carries all four things at once -- the most complete vehicle model,
flexible wheelsets, a compliant track and the CN60-1100-1:18 turnout geometry -- and every earlier
case carried at most three of them:

* ``vehicles/turnouts/CN60-1100-1_18/cases/straight.json``: turnout geometry + compliant track, but
  a 7-body rigid-wheelset vehicle (35 vehicle coordinates);
* ``examples/portable/case_flexible.json``: flexible wheelsets, but 12 synthetic stations and a rigid
  track;
* ``vehicles/CRH380A_M_axlebox.json``: the complete model (8 axle boxes, 15 bodies, 86 vehicle
  coordinates) with **no case at all**.

Nothing here re-derives the car or the track: the case points at the vehicle model through
``vehicle_ref`` (so there is one definition of the car, not a copy that drifts) and keeps the
turnout's own ``rail_templates``, ``track_dynamics``, ``run`` and ``contact`` blocks byte for byte.
What this script adds is the two blocks that make them coexist: ``vehicle_ref`` and
``flexible_wheelset``.

    PYTHONPATH=src python -X utf8 scripts/s101_one_set_case.py --dry
    PYTHONPATH=src python -X utf8 scripts/s101_one_set_case.py --seat
    PYTHONPATH=src python -X utf8 scripts/s101_one_set_case.py --duration 0.02 --archive

``--seat`` is the first gate on purpose: if the static vertical equilibrium cannot be found for the
86-coordinate car on this track, a longer run only hides that.
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import json
import pathlib
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "vehicles/turnouts/CN60-1100-1_18/cases/straight.json"
OUT = ROOT / "vehicles/turnouts/CN60-1100-1_18/cases/straight_one_set.json"
VEHICLE_REF = "lib:CRH380A_M_axlebox.json"
MODES_REF = "lib:modes/CRH3C_wheelset_fe.json"
AXLES = (1, 2, 3, 4)


def build(base: pathlib.Path = BASE, vehicle_ref: str = VEHICLE_REF,
          modes_ref: str = MODES_REF, flexible: bool = True,
          duration_s: float | None = None, speed_kmh: float = 80.0) -> dict:
    raw = json.loads(base.read_text(encoding="utf-8"))
    case = copy.deepcopy(raw)
    if "vehicle" not in case:
        raise SystemExit(f"{base}: the base case has no 'vehicle' block to replace")
    case.pop("vehicle")
    case["vehicle_ref"] = vehicle_ref
    if flexible:
        case["flexible_wheelset"] = {"source": "file", "file": modes_ref,
                                     "axles": list(AXLES)}
    else:
        case.pop("flexible_wheelset", None)
    case["case_id"] = "turnout_cn60_1100_straight_one_set" + ("" if flexible else "_rigid_wheelsets")
    # ``purpose`` is a closed vocabulary ("synthetic" | "engineering"); what this case is
    # belongs in ``purpose_detail``, which is free text.
    case["purpose_detail"] = (
        "一组模型：完备车辆（" + vehicle_ref + "，15 体 86 坐标含 8 轴箱）"
        + ("+ 柔性轮对（" + modes_ref + "）" if flexible else "（刚性轮对）")
        + " + 柔性轨道（local_compliant）+ CN60-1100-1:18 真道岔几何。"
          "车辆的唯一定义在 vehicle_ref，轨道与接触块原样继承 straight.json。")
    case["source_evidence"] = dict(case.get("source_evidence") or {})
    case["source_evidence"]["derived_from"] = str(base.relative_to(ROOT)).replace("\\", "/")
    case["source_evidence"]["vehicle_ref"] = vehicle_ref
    if flexible:
        case["source_evidence"]["flexible_wheelset"] = modes_ref
    # The vehicle model carries its own design speed (350 km/h on open line).  On a turnout the
    # running speed is a property of the *case*, not of the car, so the case states it here -- the
    # loader turns a constant ``speed_profile`` into ``vehicle.travel_speed_m_s`` (``speed.py:118``),
    # which keeps one definition of the car and no duplicated scalar.
    run = dict(case["run"])
    run["speed_profile"] = {"constant": {"speed_kmh": float(speed_kmh)}}
    if duration_s is not None:
        run["duration_s"] = float(duration_s)
    case["run"] = run
    return case


def describe(case: dict) -> dict:
    """What the loader made of it -- dimension first, because that is where a merge usually fails."""
    from velch.topology import topology_of
    from velch.vehicle import load_vehicle_case

    target = OUT
    target.write_text(json.dumps(case, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    loaded = load_vehicle_case(target)
    # ``VehicleCase.topology`` is the raw block; the parsed topology is what carries the dimension.
    topology = topology_of(loaded.topology, loaded.vehicle)
    vehicle_dof = topology.body_dimension
    modes = getattr(loaded, "wheel_modes", None)
    modal = sum(len(item.modes) for item in modes.values()) if modes else 0
    bodies: dict[str, int] = {}
    for body in topology.bodies:
        bodies[body.kind] = bodies.get(body.kind, 0) + 1
    return {
        "case": str(target),
        "case_id": loaded.case_id,
        "track_kind": loaded.track_kind,
        # VehicleCase has no ``dimension`` field; the layout lives in ``initial_q``.
        "dimension": len(loaded.initial_q),
        "vehicle_dof": vehicle_dof,
        "modal_dof": modal,
        "bodies": bodies,
        "bodies_total": len(topology.bodies),
        "track_layers": len(loaded.track_layers or ()),
        "rails": len(loaded.rails),
        "rail_bodies": sum(len(rail.contact_bodies) for rail in loaded.rails),
        "speed_kmh": loaded.vehicle.travel_speed_m_s * 3.6,
        "duration_s": loaded.run.duration_s,
    }


def seat_and_report(case) -> int:
    from velch.vehicle_solver import VehicleDynamics, _static_vertical_equilibrium

    dynamics = VehicleDynamics(case)
    try:
        speed = float(case.vehicle.travel_speed_m_s)
        velocity = np.zeros(dynamics.dimension)
        for body in dynamics.topology.bodies:
            spin = dynamics.topology.index(body.id, "spin")
            if spin is not None:
                velocity[spin] = speed / case.vehicle.nominal_wheel_radius_m
        started = time.perf_counter()
        state, residual = _static_vertical_equilibrium(
            case, dynamics, np.array(case.initial_q, dtype=float), velocity)
        wall = time.perf_counter() - started
        force, contacts = dynamics.evaluate(0.0, np.asarray(state, dtype=float), velocity)
        weight = sum(body.mass_kg for body in dynamics.topology.bodies) * case.vehicle.gravity_m_s2
        print(f"dimension {dynamics.dimension}  seat residual {residual:.3e} N  wall {wall:.1f} s")
        print(f"total weight {weight:.1f} N")
        worst = 0.0
        for rail in case.rails:
            response = contacts[rail.id]
            share = response.normal_force_n / (weight / 8.0) if response.active else 0.0
            worst = max(worst, abs(share - 1.0)) if response.active else worst
            print(f"  {rail.id:<14} N {response.normal_force_n:10.1f}  share {share:6.3f}"
                  f"  active {response.active}  pen {getattr(response.geometry, 'penetration_m', 0.0) * 1e6:8.2f} um")
        print(f"worst |share-1| {worst:.3f}")
        ok = abs(residual) <= 0.1 and worst <= 0.6
        print("SEAT " + ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    finally:
        dynamics.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=pathlib.Path, default=BASE)
    ap.add_argument("--vehicle-ref", default=VEHICLE_REF)
    ap.add_argument("--modes", default=MODES_REF)
    ap.add_argument("--rigid-wheelsets", action="store_true")
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--speed-kmh", type=float, default=80.0,
                    help="running speed written into run.speed_profile (override with --speed-kmh)")
    ap.add_argument("--dry", action="store_true", help="write the case, load it, print the dimension")
    ap.add_argument("--seat", action="store_true", help="static vertical equilibrium + per-rail loads")
    ap.add_argument("--archive", action="store_true",
                    help="run it through scripts/s99_run_archive.py so the data is kept")
    args = ap.parse_args()

    case = build(args.base, args.vehicle_ref, args.modes,
                 flexible=not args.rigid_wheelsets, duration_s=args.duration,
                 speed_kmh=args.speed_kmh)
    info = describe(case)
    for key, value in info.items():
        print(f"{key}: {value}")
    if args.dry:
        return 0

    from velch.vehicle import load_vehicle_case

    loaded = load_vehicle_case(OUT)
    if args.seat:
        return seat_and_report(loaded)
    if args.archive:
        import subprocess
        import sys

        command = [sys.executable, "-X", "utf8", "scripts/s99_run_archive.py",
                   "--route", "straight", "--duration", str(args.duration or 0.02),
                   "--note", "model=one_set", "--note", f"vehicle={args.vehicle_ref}"]
        print("running:", " ".join(command))
        return subprocess.call(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
