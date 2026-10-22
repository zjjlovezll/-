# -*- coding: utf-8 -*-
"""Build a frog-window case whose track uses the SDITT flexible-track parameters.

SDITT (validation/turnout18_ref/sditt_dump/Par_TrackSystem.m, FT-Modal block):
    rail pad   k = 25e6 N/m, c = 20e3 N s/m   (k_y 20e6, c_y 20e3 in the pad block)
    sleeper    mass 79 kg
    ballast    k = 12e6 N/m, c = 120e3 N s/m
Those are the numbers S1F_TRACK_LAYERS_2026-10-20.md derived the 32.0 Hz series
mode from, so a `layered` stack with one sleeper layer is the Velch rendering of
the same physical track.
"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
BASE = HERE / "case_frog_N_strip05.json"

PAD = {"k_y_n_m": 20.0e6, "c_y_n_s_m": 20.0e3, "k_z_n_m": 25.0e6, "c_z_n_s_m": 20.0e3}
BALLAST = {
    "mass_y_kg": 79.0, "mass_z_kg": 79.0,
    "k_y_n_m": 10.0e6, "c_y_n_s_m": 100.0e3,
    "k_z_n_m": 12.0e6, "c_z_n_s_m": 120.0e3,
}


def build(name: str, duration_s: float, output_step_s: float) -> pathlib.Path:
    data = json.loads(BASE.read_text(encoding="utf-8"))
    data["case_id"] = name
    for template in data["rail_templates"]:
        support = dict(template.get("support", {}))
        support.update(PAD)
        template["support"] = support
    data["track_dynamics"] = {"kind": "layered", "layers": [BALLAST]}
    data["run"]["duration_s"] = duration_s
    data["run"]["output_step_s"] = output_step_s
    data.pop("initial_state", None)
    path = HERE / f"case_{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(build("sditt_layered_0p05s", 0.05, 5e-4))
