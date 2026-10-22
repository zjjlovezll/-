"""Build two-layer track cases (rail + sleeper + ballast) from the kz50/cz20 base.

Per rail and per axis, per sleeper pitch of 0.6 m (SDITT Par_TrackSystem.m,
Flexible Track path):

    rail    m = 121 kg   (2 m of 60.64 kg/m)
    pad     kz = 25e6 N/m, cz = 20e3 N.s/m      (120e6/m * 0.6)
    sleeper m = 79 kg    (2400 kg/m^3 * 0.054824 m^2 * 0.6 = 131.6 kg/m * 0.6)
    ballast kz = 12e6 N/m, cz = 120e3 N.s/m     (20e6/m * 0.6, 200e3/m * 0.6)
    lateral: pad 25e6, ballast 6e6 / 60e3       (10e6/m * 0.6, 100e3/m * 0.6)

In-phase eigenfrequency sqrt(k_series/(m_r+m_s))/2pi = 32.0 Hz; out-of-phase
sqrt(k_pad*(1/m_r+1/m_s))/2pi ~ 190 Hz. Reference solver: 31.65 Hz dominant.
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
BASE = HERE / "case_Z_full_cz20.json"

SUPPORT = {
    "k_y_n_m": 25.0e6,
    "c_y_n_s_m": 20.0e3,
    "k_z_n_m": 25.0e6,
    "c_z_n_s_m": 20.0e3,
    "sleeper_mass_y_kg": 79.0,
    "sleeper_mass_z_kg": 79.0,
    "ballast_k_y_n_m": 6.0e6,
    "ballast_c_y_n_s_m": 60.0e3,
    "ballast_k_z_n_m": 12.0e6,
    "ballast_c_z_n_s_m": 120.0e3,
}
RAIL_MASS = 121.0


def build(tag: str, *, duration: float, x_start: float, step: float) -> pathlib.Path:
    raw = json.loads(BASE.read_text(encoding="utf-8"))
    raw["case_id"] = f"crh380a_m_two_layer_{tag}"
    raw["purpose_detail"] = (
        "two-layer track (rail + sleeper + ballast): the S1-f conclusion that a "
        "single lumped track DOF cannot hold both the frog peak and the 30-60 Hz band"
    )
    raw["track_dynamics"] = {"kind": "two_layer"}
    for template in raw["rail_templates"]:
        template["mass_y_kg"] = RAIL_MASS
        template["mass_z_kg"] = RAIL_MASS
        template["support"] = dict(SUPPORT)
    rails = len(raw["rail_templates"]) * 4
    n = 35 + 4 * rails
    state = raw.get("initial_state", {})
    state["q"] = [0.0] * n
    state["v"] = [0.0] * n
    raw["initial_state"] = state
    raw["run"]["duration_s"] = duration
    raw["run"]["x_start_m"] = x_start
    raw["run"]["output_step_s"] = step
    out = HERE / f"case_AA_{tag}.json"
    out.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out.name}: rails={rails} dof={n} duration={duration} x_start={x_start}")
    return out


build("frog_two_layer", duration=0.05, x_start=69.0, step=0.0005)
build("full_two_layer", duration=1.2, x_start=13.5, step=0.0005)
