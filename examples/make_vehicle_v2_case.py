"""Make a four-axle synthetic turnout case with SDITT-sourced vehicle scalars.

The wheel/rail profiles and longitudinal turnout transfer are synthetic. The
SDITT parameter values are cited, not asserted to be calibrated for this case.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent / "vehicle_v2"
ROOT.mkdir(parents=True, exist_ok=True)
MATLAB_SOURCE = Path(r"G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728\Par_Vehicle_CRH380A_v6.m")


def profile(name: str, center_y: float, height: float, wheel: bool = False) -> str:
    path = ROOT / name
    lateral = np.linspace(-0.045, 0.045, 81) if wheel else np.linspace(-0.03, 0.03, 61)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        for y in lateral:
            z = -0.43 + y * y / (2 * 0.43) if wheel else height - y * y / (2 * 0.12)
            writer.writerow((f"{center_y + y:.12f}", f"{z:.12f}"))
    return name


wheel_file = profile("wheel_lower.csv", 0, 0, True)
rail_support = {"k_y_n_m": 5e8, "c_y_n_s_m": 2e4,
                "k_z_n_m": 4e8, "c_z_n_s_m": 1e4}


def rail_template(name: str, wheel_id: str, center_y: float, heights: tuple[float, ...]) -> dict:
    stations = []
    for index, (s, h) in enumerate(zip((-1.0, 20.005, 20.02, 25.0), heights)):
        filename = profile(f"{name}_{index}.csv", center_y, h)
        stations.append({"id": f"{name}_{index}", "s_m": s,
                         "profile": {"file": filename, "format": "csv", "units": "m"}})
    return {"id": name, "wheel_id": wheel_id, "mass_y_kg": 120.0,
            "mass_z_kg": 120.0, "support": rail_support, "stations": stations}


primary = {"k_y_n_m": 980000.0, "c_y_n_s_m": 0.0,
           "k_z_n_m": 1176000.0, "c_z_n_s_m": 10000.0,
           "k_yaw_nm_rad": 2 * 980000.0 * (2.00 / 2) ** 2,
           "c_yaw_nm_s_rad": 0.0, "half_width_m": 2.00 / 2,
           "upper_anchor_height_m": -(0.51 - 0.43), "lower_anchor_height_m": 0.0}
secondary = {"k_y_n_m": 168900.0, "c_y_n_s_m": 0.0,
             "k_z_n_m": 260000.0, "c_z_n_s_m": 40000.0,
             "k_yaw_nm_rad": 2 * 168900.0 * (2.46 / 2) ** 2,
             "c_yaw_nm_s_rad": 0.0, "half_width_m": 2.46 / 2,
             "upper_anchor_height_m": -(1.52 - 1.0),
             "lower_anchor_height_m": 0.8 - 0.51}

case = {
    "schema_version": "velch-vehicle-v2",
    "case_id": "synthetic_four_axle_turnout_v2",
    "purpose": "synthetic",
    "parameter_source": "SDITT Par_Vehicle_CRH380A_v6.m selected mass/inertia/linear suspension values; synthetic wheel/rail geometry and independent connector equations",
    "source_evidence": {
        "matlab_file": str(MATLAB_SOURCE),
        "matlab_sha256": hashlib.sha256(MATLAB_SOURCE.read_bytes()).hexdigest(),
        "simpack_role": "object hierarchy only; no internal vehicle equation recovered",
    },
    "vehicle": {
        "carbody": {"mass_kg": 33766.0 + 7074.0,
                    "roll_inertia_kg_m2": 110200.0,
                    "pitch_inertia_kg_m2": 1666000.0,
                    "yaw_inertia_kg_m2": 1572200.0},
        "bogie": {"mass_kg": 2280.0, "roll_inertia_kg_m2": 1847.0,
                  "pitch_inertia_kg_m2": 1249.0, "yaw_inertia_kg_m2": 2280.0},
        "wheelset": {"mass_kg": 1901.8, "roll_inertia_kg_m2": 685.0,
                     "spin_inertia_kg_m2": 76.0, "yaw_inertia_kg_m2": 685.0},
        "primary": primary, "secondary": secondary,
        "bogie_half_spacing_m": 17.50 / 2, "wheelbase_m": 2.50,
        "wheel_center_height_m": 0.43, "nominal_wheel_radius_m": 0.43,
        "travel_speed_m_s": 2.0, "gravity_m_s2": 9.81,
        "drive_torque_per_wheelset_nm": 0.0,
    },
    "contact": {"normal_model": "hertz_effective_radius", "damping_model": "delta_half_velocity",
                "tangential_model": "sditt_cubic_saturation", "effective_modulus_pa": 1e11,
                "effective_radius_m": 0.02, "normal_damping_n_s_m_1p5": 1e6,
                "friction_coefficient": 0.35, "creep_stiffness_x_n": 1e6,
                "creep_stiffness_lateral_n": 5e5, "reference_speed_floor_m_s": 0.1},
    "wheels": [{"id": side, "lateral_offset_m": offset,
                "profile": {"file": wheel_file, "format": "csv", "units": "m"}}
               for side, offset in (("L", -0.75), ("R", 0.75))],
    "rail_templates": [
        rail_template("left_stock", "L", -0.75, (0.0, 0.0, 0.0, 0.0)),
        rail_template("right_stock", "R", 0.755, (0.0, 0.0, -0.0008, -0.0008)),
        rail_template("right_switch", "R", 0.735, (-0.0008, -0.0008, 0.0, 0.0)),
    ],
    "equilibrate_vertical": True,
    "run": {"method": "DOP853", "x_start_m": 10.0, "duration_s": 0.015,
            "output_step_s": 0.0005, "max_solver_step_s": 0.0001,
            "rtol": 1e-6, "atol": 1e-8, "maximum_penetration_m": 0.003,
            "maximum_abs_contact_slope": 1.0},
}
q = [0.0] * (35 + 2 * 12)
for axle in range(4):
    q[5 * axle + 1] = -0.00025
case["initial_state"] = {"q": q}
(ROOT / "case.json").write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(ROOT / "case.json")
