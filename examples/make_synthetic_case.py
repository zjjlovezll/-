"""Generate a transparent *synthetic* turnout transfer demonstration case.

These values are not the user's 07(009) or H-drive Simpack engineering inputs.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent / "synthetic_transfer"
ROOT.mkdir(parents=True, exist_ok=True)


def write_profile(name: str, center_y: float, height: float, *, wheel: bool = False) -> str:
    path = ROOT / name
    lateral = np.linspace(-0.045, 0.045, 121) if wheel else np.linspace(-0.03, 0.03, 81)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        for dy in lateral:
            z = -0.46 + dy * dy / (2 * 0.46) if wheel else height - dy * dy / (2 * 0.12)
            writer.writerow((f"{center_y + dy:.12f}", f"{z:.12f}"))
    return name


wheel_file = write_profile("wheel_lower.csv", 0.0, 0.0, wheel=True)
support = {"k_y_n_m": 5e7, "c_y_n_s_m": 2e4, "k_z_n_m": 4e7, "c_z_n_s_m": 1e4}


def rail(name: str, wheel_id: str, center_y: float, heights: list[float]) -> dict:
    stations = []
    for index, (s, height) in enumerate(zip((0.0, 0.06, 0.12), heights)):
        filename = write_profile(f"{name}_{index}.csv", center_y, height)
        stations.append({"id": f"{name}_{index}", "s_m": s,
                         "profile": {"file": filename, "format": "csv", "units": "m"}})
    return {"id": name, "wheel_id": wheel_id, "mass_y_kg": 120.0,
            "mass_z_kg": 120.0, "support": support, "stations": stations}


rails = [
    rail("left_stock", "L", -0.75, [0.0, 0.0, 0.0]),
    rail("right_stock", "R", 0.755, [0.0, -0.0015, -0.003]),
    rail("right_switch", "R", 0.735, [-0.003, -0.0015, 0.0]),
]
case = {
    "schema_version": "velch-case-v1",
    "case_id": "synthetic_two_rail_transfer_v1",
    "purpose": "synthetic",
    "parameter_source": "invented transparent demonstration values; not engineering calibration",
    "wheelset": {"mass_kg": 1800.0, "roll_inertia_kg_m2": 780.0,
                 "spin_inertia_kg_m2": 120.0, "gravity_m_s2": 9.81,
                 "travel_speed_m_s": 2.0, "drive_torque_nm": 0.0},
    "suspension": {"k_y_n_m": 1e6, "c_y_n_s_m": 1e4,
                   "k_z_n_m": 0.0, "c_z_n_s_m": 0.0,
                   "k_roll_nm_rad": 2e6, "c_roll_nm_s_rad": 1e4,
                   "y_reference_m": 0.0, "z_reference_m": 0.46,
                   "roll_reference_rad": 0.0},
    "contact": {"normal_model": "hertz_effective_radius",
                "damping_model": "delta_half_velocity",
                "tangential_model": "sditt_cubic_saturation",
                "effective_modulus_pa": 1e11, "effective_radius_m": 0.02,
                "normal_damping_n_s_m_1p5": 1e6, "friction_coefficient": 0.35,
                "creep_stiffness_x_n": 1e6, "creep_stiffness_lateral_n": 5e5,
                "reference_speed_floor_m_s": 0.1},
    "wheels": [
        {"id": "L", "lateral_offset_m": -0.75,
         "profile": {"file": wheel_file, "format": "csv", "units": "m"}},
        {"id": "R", "lateral_offset_m": 0.75,
         "profile": {"file": wheel_file, "format": "csv", "units": "m"}},
    ],
    "rails": rails,
    "run": {"method": "DOP853", "x_start_m": 0.0, "duration_s": 0.06, "output_step_s": 0.001,
            "max_solver_step_s": 0.00025, "rtol": 1e-6, "atol": 1e-8,
            "maximum_penetration_m": 0.003, "maximum_abs_contact_slope": 1.0},
    "initial_state": {
        "wheel_q": {"y_m": 0.0, "z_m": 0.461, "roll_rad": 0.0, "spin_rad": 0.0},
        "wheel_v": {"y_m_s": 0.0, "z_m_s": 0.0, "roll_rad_s": 0.0,
                    "spin_rad_s": 2.0 / 0.46},
        "rail_q": {item["id"]: {"y_m": 0.0, "z_m": 0.0} for item in rails},
        "rail_v": {item["id"]: {"y_m_s": 0.0, "z_m_s": 0.0} for item in rails},
    },
}
(ROOT / "case.json").write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(ROOT / "case.json")
