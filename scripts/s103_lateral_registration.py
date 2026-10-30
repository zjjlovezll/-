"""M2 diagnosis: with the honest contact stiffness, where does the wheel actually touch, and how
does the contact move when the wheelset is shifted sideways?

B047 has been described three ways in this project -- "the lateral stiffness is 927 times too hard",
"the contact angle does not respond to lateral shift", "the contact sits 16.7 mm inboard of the
crown" -- and every one of those numbers was measured while the case still used a 20 mm effective
radius, i.e. a contact 12-27 times sharper than the drawn geometry (B048, retired).  So the first
move of M2 is not a fix: it is to re-measure the registration on the current stiffness.

What is measured, per lateral shift dy of wheelset 1 (no re-seating: the seat belongs to dy = 0):

  lever_y       absolute lateral position of the contact (m)
  crown_y       the drawn crown of that rail at the same station (max z of the profile)
  contact_on_crown    |lever_y - crown_y| <= 2 mm -- the new gate the task book names
  d(lever_y)/dy      1.0 means the contact follows the wheel; 0.0 means it is pinned
  n_y/n_z       the local contact-plane tilt -- this is what feeds lateral force on a crowned rail
  k_lat         d(sum Fy of the two rails of axle 1)/dy, kN/mm

The pre-registered M2 targets (task book) are d(lever_y)/dy in [0.5, 1.0], a monotone k_lat of
10-100 kN/mm with no loss of contact over +-3 mm, and tan(tau) growing from 0.025 towards >= 0.3 at
the flange root (that last one needs a larger shift than +-3 mm, so it is reported as a trend only).

    PYTHONPATH=src python -X utf8 scripts/s103_lateral_registration.py
    PYTHONPATH=src python -X utf8 scripts/s103_lateral_registration.py --write
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s103"
SPEED_M_S = 80.0 / 3.6
ROLL_RADIUS_M = 0.43
AXLE = "axle1"
SHIFTS_MM = (-3.0, -2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 3.0)
ON_CROWN_TOL_M = 2.0e-3


def crown_y(series, station_m: float) -> float:
    """Lateral position of the drawn crown (max z) of one rail body at one station."""
    sample = series.sample(station_m, 1.0)
    index = int(np.argmax(sample.profile.z_m))
    return float(sample.profile.y_m[index])


def read(merged_frame, dynamics, rail_ids) -> dict:
    """Per rail: merged response plus the per-body split, so a second body cannot hide a contact."""
    frame = dynamics.body_contacts
    out: dict[str, dict] = {}
    for rail_id in rail_ids:
        bodies = frame.get(rail_id) or ()
        merged = merged_frame.get(rail_id)
        best = None
        for response in bodies:
            if response.active and response.geometry is not None:
                if best is None or response.geometry.penetration_m > best.geometry.penetration_m:
                    best = response
        geometry = best.geometry if best is not None else None
        out[rail_id] = {
            "normal_n": float(merged.normal_force_n) if merged is not None else 0.0,
            "lateral_n": float(merged.wheel_force_y_n) if merged is not None else 0.0,
            "active": bool(merged is not None and merged.active),
            "lever_y": None if geometry is None else float(geometry.lever_y_m),
            "penetration_m": None if geometry is None else float(geometry.penetration_m),
            "tilt": None if geometry is None else float(geometry.normal_y / geometry.normal_z),
            "bodies": len([r for r in bodies if r.active and r.geometry is not None]),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    # ``_seat`` works on numpy vectors (it indexes with arrays), so keep them arrays here too.
    state = np.asarray(case.initial_q, dtype=float)
    velocity = np.asarray(case.initial_v, dtype=float)
    spin = dynamics.topology.require("wheelset1", "spin")
    velocity[spin] = SPEED_M_S / ROLL_RADIUS_M
    seated, residual = _seat(case, dynamics, state, velocity)
    state = np.asarray(seated, dtype=float)
    print(f"seat residual {residual:.3e} N")
    y_index = dynamics.topology.require("wheelset1", "y")

    station = float(case.run.x_start_m) + float(case.vehicle.axle_offsets_m[0])
    rails = {rail.id: rail for rail in case.rails}
    rail_ids = [f"{AXLE}_left", f"{AXLE}_right"]
    # The crown comes from the stock body: on the right side the blade is still 15 mm down at this
    # station and must not be mistaken for the running surface.
    crowns = {rail_id: crown_y(rails[rail_id].contact_bodies[0].series, station)
              for rail_id in rail_ids}

    rows = []
    for shift_mm in SHIFTS_MM:
        q = state.copy()
        q[y_index] = state[y_index] + shift_mm * 1e-3
        # ``evaluate`` returns ``(rhs, contacts)``.
        _, merged_frame = dynamics.evaluate(0.0, q, velocity)
        reading = read(merged_frame, dynamics, rail_ids)
        row = {"shift_mm": shift_mm, "contacts": reading,
               "sum_lateral_n": sum(reading[r]["lateral_n"] for r in rail_ids),
               "sum_normal_n": sum(reading[r]["normal_n"] for r in rail_ids)}
        rows.append(row)

    by_shift = {row["shift_mm"]: row for row in rows}
    base = by_shift[0.0]
    summary = {
        "case": str(CASE),
        "station_m": station,
        "speed_kmh": SPEED_M_S * 3.6,
        "crown_y": crowns,
        "seat_residual_note": "seat taken at dy=0; other rows evaluate without re-seating",
        "rows": rows,
    }
    for rail_id in rail_ids:
        levers = [(row["shift_mm"], row["contacts"][rail_id]["lever_y"]) for row in rows]
        slopes = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(levers, levers[1:])
                  if a[1] is not None and b[1] is not None and b[0] != a[0]]
        slope = None
        if slopes:
            num = sum(ds * dl for ds, dl in slopes)
            den = sum(ds * ds for ds, _ in slopes)
            slope = num / den
        summary[f"d_lever_y_dy_{rail_id}"] = slope
        lever0 = base["contacts"][rail_id]["lever_y"]
        summary[f"contact_on_crown_{rail_id}"] = (
            None if lever0 is None else abs(lever0 - crowns[rail_id]) <= ON_CROWN_TOL_M)
        summary[f"lever_minus_crown_mm_{rail_id}"] = (
            None if lever0 is None else (lever0 - crowns[rail_id]) * 1e3)
        summary[f"lost_contact_{rail_id}"] = [row["shift_mm"] for row in rows
                                             if not row["contacts"][rail_id]["active"]]

    lateral = [(row["shift_mm"], row["sum_lateral_n"]) for row in rows]
    num = sum((b[0] - a[0]) * 1e-3 * (b[1] - a[1]) for a, b in zip(lateral, lateral[1:]))
    den = sum(((b[0] - a[0]) * 1e-3) ** 2 for a, b in zip(lateral, lateral[1:]))
    summary["k_lateral_kn_per_mm"] = num / den / 1e3 if den else None
    summary["k_lateral_sign_note"] = "positive means the track pushes back against +y"

    print(f"station {station:.3f} m   crowns  left {crowns[rail_ids[0]] * 1e3:+.3f} mm  "
          f"right {crowns[rail_ids[1]] * 1e3:+.3f} mm")
    print(f"{'dy(mm)':>7} {'left lever':>11} {'left N':>9} {'left tilt':>10} "
          f"{'right lever':>12} {'right N':>9} {'right tilt':>11} {'sum Fy':>9}")
    for row in rows:
        left = row["contacts"][rail_ids[0]]
        right = row["contacts"][rail_ids[1]]
        fmt = lambda value, scale, width: ("       -" if value is None else f"{value * scale:>{width}.3f}")
        print(f"{row['shift_mm']:>7.1f} {fmt(left['lever_y'], 1e3, 11)} {left['normal_n'] / 1e3:>9.2f} "
              f"{fmt(left['tilt'], 1, 10)} {fmt(right['lever_y'], 1e3, 12)} "
              f"{right['normal_n'] / 1e3:>9.2f} {fmt(right['tilt'], 1, 11)} "
              f"{row['sum_lateral_n'] / 1e3:>9.2f}")
    for rail_id in rail_ids:
        print(f"{rail_id}: d(lever_y)/dy {summary[f'd_lever_y_dy_{rail_id}']:.4f}   "
              f"lever-crown {summary[f'lever_minus_crown_mm_{rail_id}']:+.3f} mm   "
              f"on crown {summary[f'contact_on_crown_{rail_id}']}   "
              f"lost at {summary[f'lost_contact_{rail_id}'] or 'never'}")
    print(f"k_lateral {summary['k_lateral_kn_per_mm']:.2f} kN/mm (target 10-100 monotone)")

    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "registration.json").write_text(
            json.dumps(summary, indent=1, ensure_ascii=False) + chr(10), encoding="utf-8")
        print(f"report -> {OUT / 'registration.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
