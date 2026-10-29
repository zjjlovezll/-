"""Where does the tread actually meet the rail crown?  Sweep the lateral registration.

B047 was measured as '-235 kN/mm, and one side loses contact at +-1 mm', with the contacts sitting
16.7 mm inboard of the crowns (docs/STRAIGHT_LATERAL_B047_2026-10-29.md).  A contact on the corner
fillet instead of the crown turns 1 mm of lateral motion into ~210 um of depth, because the fillet's
slope is far steeper than the 1:40 tread.

This probe asks one question and answers it by measurement: for which wheel/rail lateral registration
does the pair behave like a wheel on a crown -- contacts within 2 mm of the crown, dFy/dy in
0.05-0.5 kN/mm, and no single-side loss within +-3 mm?

It changes nothing in `src/`: the registration is a case-level wheel offset, so a wrong value cannot
be mistaken for a physics change.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat

EVEN_SHARE_N = 59_662.0
CROWN_M = 0.75325
OFFSETS_MM = (0.0, 4.0, 8.0, 10.0, 12.0, -4.0, -8.0)


def build(source: Path, offset_mm: float, target: Path) -> Path:
    raw = json.loads(source.read_text(encoding="utf-8"))
    half = 0.7465 + offset_mm * 1e-3
    for wheel in raw["wheels"]:
        wheel["lateral_offset_m"] = -half if wheel["id"] == "L" else half
    raw["run"].update(x_start_m=40.0, seat_x_start_m=40.0, duration_s=1e-3, output_step_s=1e-3)
    raw.pop("initial_state", None)
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return target


def seated(case_path: Path):
    case = load_vehicle_case(case_path)
    dynamics = VehicleDynamics(case)
    velocity = np.zeros(dynamics.dimension)
    speed = case.vehicle.travel_speed_m_s / case.vehicle.nominal_wheel_radius_m
    for body in dynamics.topology.bodies:
        if "spin" in body.dof:
            velocity[dynamics.topology.require(body.id, "spin")] = speed
    q, residual = _seat(case, dynamics, np.zeros(dynamics.dimension), velocity)
    return case, dynamics, q, velocity, residual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="../scratch/s73/case_s40.json")
    parser.add_argument("--out", default="../scratch/s74")
    options = parser.parse_args()

    source = Path(options.case)
    out = Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"{'offset':>7}{'seat':>11}{'left pen':>10}{'right pen':>10}"
          f"{'leverL-crown':>14}{'leverR-crown':>14}{'dFy/dy kN/mm':>14}{'loses':>7}")
    rows = []
    for offset_mm in OFFSETS_MM:
        case_path = build(source, offset_mm, out / f"case_off{offset_mm:+.0f}.json")
        try:
            case, dynamics, q, velocity, residual = seated(case_path)
        except Exception as exc:  # seat is the first thing that tells us the pair is wrong
            print(f"{offset_mm:+7.1f}{'FAILED':>11}  {str(exc)[:80]}")
            continue
        index = dynamics.topology.require("wheelset1", "y")
        finds = {}
        for dy_mm in (-3.0, -1.0, 0.0, 1.0, 3.0):
            state = q.copy()
            state[index] += dy_mm * 1e-3
            _f, contacts = dynamics.evaluate(0.0, state, velocity)
            pair = [c for c in (contacts.get("axle1_left"), contacts.get("axle1_right"))
                    if c is not None and getattr(c, "geometry", None) is not None]
            finds[dy_mm] = (sum(float(c.wheel_force_y_n) for c in pair), pair)
        slope = (finds[-3.0][0] - finds[3.0][0]) / 6e-3 / 1e3
        centre = finds[0.0][1]
        if not centre:
            print(f"{offset_mm:+7.1f}{residual:11.2e}  no contact at centre")
            continue
        left = next((c for c in centre if c.geometry.lever_y_m < 0), None)
        right = next((c for c in centre if c.geometry.lever_y_m > 0), None)
        loses = any(len(finds[dy][1]) < 2 for dy in (-1.0, 1.0))
        row = {
            "offset_mm": round(offset_mm, 1),
            "seat_residual_n": float(residual),
            "left_pen_um": float(left.geometry.penetration_m * 1e6) if left else None,
            "right_pen_um": float(right.geometry.penetration_m * 1e6) if right else None,
            "left_lever_minus_crown_mm": float((left.geometry.lever_y_m + CROWN_M) * 1e3) if left else None,
            "right_lever_minus_crown_mm": float((right.geometry.lever_y_m - CROWN_M) * 1e3) if right else None,
            "d_fy_dy_kn_per_mm": float(slope),
            "loses_contact_within_3mm": bool(loses),
        }
        rows.append(row)
        print(f"{offset_mm:+7.1f}{residual:11.2e}"
              f"{(row['left_pen_um'] or float('nan')):10.2f}{(row['right_pen_um'] or float('nan')):10.2f}"
              f"{(row['left_lever_minus_crown_mm'] or float('nan')):+14.2f}"
              f"{(row['right_lever_minus_crown_mm'] or float('nan')):+14.2f}"
              f"{slope:14.2f}{'yes' if loses else 'no':>7}")
    (out / "registration_sweep.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    good = [r for r in rows if not r["loses_contact_within_3mm"]
            and 0.05 <= abs(r["d_fy_dy_kn_per_mm"]) <= 0.5
            and abs(r["left_lever_minus_crown_mm"] or 99) <= 2.0
            and abs(r["right_lever_minus_crown_mm"] or 99) <= 2.0]
    print(f"registrations meeting the crown criterion: {[r['offset_mm'] for r in good]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
