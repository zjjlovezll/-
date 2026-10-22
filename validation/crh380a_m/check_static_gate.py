"""Static gate: does the compliant fastener keep 59 680.577 N and a Hertzian penetration?"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_flat_S_local.json"
DONOR = BASE / "case_Z_local_rail.json"


def build(soft: bool) -> Path:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    donor = json.loads(DONOR.read_text(encoding="utf-8"))
    raw["track_dynamics"] = dict(donor["track_dynamics"])
    extra = len(donor["initial_state"]["q"]) - len(raw["initial_state"]["q"])
    raw["initial_state"]["q"] = list(raw["initial_state"]["q"]) + [0.0] * extra
    if soft:
        for template in raw["rail_templates"]:
            template["support"]["k_z_n_m"] = 5.0e7
            template["support"]["c_z_n_s_m"] = 4.0e4
    raw["case_id"] = "flat_static_soft" if soft else "flat_static_stiff"
    path = BASE / f"case_{raw['case_id']}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def report(soft: bool) -> None:
    case = load_vehicle_case(build(soft))
    result = simulate_vehicle(case)
    first = next(iter(result.contacts))
    values = list(result.contacts[0].values()) if isinstance(result.contacts[0], dict) else []
    forces = np.array([item.normal_force_n for item in values], dtype=float)
    penetrate = np.array([(item.geometry.penetration_m if item.geometry else 0.0) for item in values], dtype=float)
    hertz = np.array([item.hertz_penetration_m for item in values], dtype=float)
    settle = np.array([item.support_settlement_m for item in values], dtype=float)
    print(f"{case.case_id:>20}  peak {forces.max():12.4f} N  min {forces.min():12.4f} N  "
          f"lost {int(np.count_nonzero(forces <= 0.0))}")
    print(f"{'':>20}  pen {1e6 * penetrate.max():7.2f} um  hertz {1e6 * hertz.max():7.2f} um  "
          f"settlement {1e6 * settle.max():7.2f} um")
    print(f"{'':>20}  summary max_pen {1e6 * result.summary['max_penetration_m']:7.2f} um  "
          f"max_hertz {1e6 * result.summary.get('max_hertz_penetration_m', float('nan')):7.2f} um")


if __name__ == "__main__":
    report(False)
    report(True)
