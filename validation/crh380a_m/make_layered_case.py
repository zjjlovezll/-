"""Build layered-track cases: L=1 equivalence check and L=2 slab-track stack.

L=1 must reproduce the two_layer kernel bit for bit (same DOF order and forces),
which is the regression that proves the generalisation is faithful.

L=2 adds the slab track that the drawing calls for (18 号单开道岔 無砟):
    rail --pad 25e6--> sleeper 79 kg --CA/垫层 120e6--> slab 300 kg --subgrade 50e6--> ground
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
BASE = HERE / "case_AA_frog_two_layer.json"

PAD = {
    "k_y_n_m": 25.0e6, "c_y_n_s_m": 20.0e3,
    "k_z_n_m": 25.0e6, "c_z_n_s_m": 20.0e3,
}
SLEEPER = {
    "mass_y_kg": 79.0, "mass_z_kg": 79.0,
    "k_y_n_m": 6.0e6, "c_y_n_s_m": 60.0e3,
    "k_z_n_m": 12.0e6, "c_z_n_s_m": 120.0e3,
}
SLEEPER_CASED = {                      # sleeper sits on the slab pad, not directly on ballast
    "mass_y_kg": 79.0, "mass_z_kg": 79.0,
    "k_y_n_m": 60.0e6, "c_y_n_s_m": 100.0e3,
    "k_z_n_m": 120.0e6, "c_z_n_s_m": 200.0e3,
}
SLAB = {
    "mass_y_kg": 300.0, "mass_z_kg": 300.0,
    "k_y_n_m": 25.0e6, "c_y_n_s_m": 200.0e3,
    "k_z_n_m": 50.0e6, "c_z_n_s_m": 400.0e3,
}


def build(tag: str, layers: list[dict], *, duration: float = 0.05, x_start: float = 69.0) -> pathlib.Path:
    raw = json.loads(BASE.read_text(encoding="utf-8"))
    raw["case_id"] = f"crh380a_m_layered_{tag}"
    raw["track_dynamics"] = {"kind": "layered", "layers": layers}
    for template in raw["rail_templates"]:
        template["support"] = dict(PAD)
    n = 35 + 2 * (1 + len(layers)) * len(raw["rail_templates"]) * 4
    raw["initial_state"] = {"q": [0.0] * n, "v": [0.0] * n}
    for axle in range(4):
        raw["initial_state"]["v"][5 * axle + 3] = raw["vehicle"]["travel_speed_m_s"] / raw["vehicle"]["nominal_wheel_radius_m"]
    raw["run"]["duration_s"] = duration
    raw["run"]["x_start_m"] = x_start
    out = HERE / f"case_AB_{tag}.json"
    out.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out.name}: layers={len(layers)} dof={n}")
    return out


build("equiv_two_layer", [SLEEPER])
build("slab3", [SLEEPER_CASED, SLAB])
