"""Where does the +718 N net lateral force come from?  Decompose one seated frame, rail by rail.

Round 245 found that the whole vehicle walks +0.73 mm in 0.40 s, and that the archived lateral forces
are +1490.4 N on each left rail and -1310.8 N on each right rail: a net +718.4 N.  The normal parts
are N*n_y = +-1478.6 N and cancel, so the net force is tangential -- per axle +11.8 N on the left and
+167.8 N on the right.  Only the right side carries a creep force, with zero lateral velocity, zero
yaw and spin = v/r.

This prints, for the seated state, every term that can make ``slip_lateral`` nonzero:

    rel_y, rel_z, tangent_y, tangent_z, creep_attack_velocity, slip_lateral, slip_x
    N, N*n_y, tangential = wheel_force_y - N*n_y, and the implied slip from the linear creep law

    PYTHONPATH=src python -X utf8 scripts/s107_lateral_creep.py [--write]
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat, _settle_modal_coordinates

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s107"
SPEED_M_S = 80.0 / 3.6
ROLL_RADIUS_M = 0.43


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    velocity = np.asarray(case.initial_v, dtype=float)
    for index in range(1, 5):
        velocity[dynamics.topology.require(f"wheelset{index}", "spin")] = SPEED_M_S / ROLL_RADIUS_M

    # Seating only is *not* the initial state the integrator starts from: `_integrate_vehicle` then
    # alternates the modal settle with the vertical seat twice, and the flexible tread is pressed
    # in by the load.  Round 245 read the archived t=0 frame, so the probe must build the same
    # state -- otherwise the two disagree for a reason that has nothing to do with the physics.
    state = np.asarray(case.initial_q, dtype=float)
    seated, residual = _seat(case, dynamics, state, velocity)
    seated = np.asarray(seated, dtype=float)
    settled = seated
    for _round in range(2):
        settled = _settle_modal_coordinates(dynamics, settled, velocity)
        settled, residual = _seat(case, dynamics, settled, velocity)
        settled = np.asarray(settled, dtype=float)

    states = {"seat only": seated, "seat + modal settle": settled}
    for label, candidate in states.items():
        print(f"--- {label}")
        report(case, dynamics, candidate, velocity, label, args.write)
    return 0


def report(case, dynamics, state, velocity, label, write) -> int:
    _, merged = dynamics.evaluate(0.0, state, velocity)
    body_contacts = dynamics.body_contacts

    rows = []
    print(f"law f22 = {case.contact.creep_stiffness_lateral_n:.3e} N   v = {SPEED_M_S:.4f} m/s")
    print(f"{'rail':>13} {'N (kN)':>8} {'Fy (N)':>9} {'N*ny':>9} {'tang':>8} {'slip_lat':>10} "
          f"{'slip_x':>9} {'n_y':>8} {'n_z':>7} {'t_y':>7} {'t_z':>8}")
    for rail in case.rails:
        response = merged[rail.id]
        bodies = [r for r in (body_contacts.get(rail.id) or ()) if r.active and r.geometry is not None]
        if not bodies:
            print(f"{rail.id:>13} inactive")
            continue
        deepest = max(bodies, key=lambda r: r.geometry.penetration_m)
        geometry = deepest.geometry
        tangential = float(response.wheel_force_y_n) - float(response.normal_force_n) * float(geometry.normal_y)
        implied_slip = (float(response.wheel_force_y_n) * SPEED_M_S
                        / max(case.contact.creep_stiffness_lateral_n, 1.0))
        row = {
            "rail": rail.id,
            "normal_n": float(response.normal_force_n),
            "wheel_force_y_n": float(response.wheel_force_y_n),
            "normal_times_ny_n": float(response.normal_force_n) * float(geometry.normal_y),
            "tangential_n": tangential,
            "slip_lateral_m_s": float(deepest.slip_lateral_m_s),
            "slip_x_m_s": float(deepest.slip_x_m_s),
            "normal_y": float(geometry.normal_y),
            "normal_z": float(geometry.normal_z),
            "lever_y_m": float(geometry.lever_y_m),
            "lever_z_m": float(geometry.lever_z_m),
            "implied_slip_from_force_m_s": implied_slip,
        }
        rows.append(row)
        print(f"{rail.id:>13} {row['normal_n'] / 1e3:>8.2f} {row['wheel_force_y_n']:>9.2f} "
              f"{row['normal_times_ny_n']:>9.2f} {tangential:>8.2f} {row['slip_lateral_m_s']:>10.6f} "
              f"{row['slip_x_m_s']:>9.6f} {row['normal_y']:>8.5f} {row['normal_z']:>7.5f} "
              f"{'':>7} {'':>8}")

    net = sum(row["wheel_force_y_n"] for row in rows)
    net_tangential = sum(row["tangential_n"] for row in rows)
    print(f"net lateral {net:+.2f} N   of which tangential {net_tangential:+.2f} N")
    print(f"[gate] |net| <= 20 N -> {'PASS' if abs(net) <= 20.0 else 'FAIL'}")

    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        payload = {"state": label, "rows": rows, "net_lateral_n": net,
                   "net_tangential_n": net_tangential, "gate_net_n": 20.0,
                   "passes": bool(abs(net) <= 20.0)}
        OUT.mkdir(parents=True, exist_ok=True)
        name = "lateral_creep.json" if label.startswith("seat +") else "lateral_creep_seat_only.json"
        (OUT / name).write_text(
            json.dumps(payload, indent=1, ensure_ascii=False) + chr(10), encoding="utf-8")
        print(f"report -> {OUT / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
