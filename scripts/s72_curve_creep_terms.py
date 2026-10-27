"""Round 72 probe v2: creep terms on straight vs curved, and the double-shift combination."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\src")

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _static_vertical_equilibrium

WORK = Path(r"F:\velch_tmp\curve72")
CASES = (
    ("straight", {"curve_radius_m": None, "curve_geometry": False}),
    ("curved_geom", {"curve_radius_m": 1100.0, "curve_geometry": True}),
    ("curved_both", {"curve_radius_m": 1100.0, "curve_geometry": True, "align_to_track": True}),
)


def build(name: str, extra: dict) -> Path:
    raw = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
    run = {"duration_s": 0.01, "output_step_s": 0.01, "x_start_m": 60.0}
    run.update(extra)
    raw["run"].update(run)
    raw["vehicle"]["travel_speed_m_s"] = 100.0 / 3.6
    raw.pop("initial_state", None)
    path = WORK / f"{name}.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    for name, extra in CASES:
        case = load_vehicle_case(build(name, extra))
        dynamics = VehicleDynamics(case, contact_workers=1)
        q = np.asarray(case.initial_q, dtype=float)
        v = np.zeros(dynamics.dimension)
        speed = float(case.vehicle.travel_speed_m_s)
        try:
            q_seated, residual = _static_vertical_equilibrium(case, dynamics, q, v)
        except Exception as error:  # noqa: BLE001 - the message is the measurement
            print(f"\n== {name}: SEAT FAILED {type(error).__name__}: {str(error)[:150]}")
            continue
        dynamics.evaluate(0.0, q_seated, v)
        patches = dynamics.body_contacts
        flat = [row for rows in patches.values() for row in rows] if patches else []
        print(f"\n== {name}: residual {residual:.2e} N, {len(flat)} patches")
        for rail in case.rails[:2]:
            index = list(case.rails).index(rail)
            x_m = float(case.run.x_start_m) + float(case.vehicle.axle_offsets_m[rail.axle_index])
            vy = float(dynamics.track.local_state(
                q_seated[dynamics.dof:], v[dynamics.dof:], index, x_m, speed)[2])
            row = next((item for item in flat if getattr(item, "rail_id", None) == rail.id), None)
            if row is None:
                print(f"  {rail.id:14s} rail vy {vy:+.6f} m/s  (no patch)")
                continue
            print(f"  {rail.id:14s} rail vy {vy:+.6f} m/s  slip_x {row.slip_longitudinal:+.3e}"
                  f"  slip_y {row.slip_lateral:+.3e}  N {row.wheel_force_z_n / 1e3:.1f} kN")
    print(f"\nfor reference, v^2/R at 100 km/h and R=1100 m = {27.7778 ** 2 / 1100.0:.3f} m/s^2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
