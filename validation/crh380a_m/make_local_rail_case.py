"""S1-e follow-up: give the rail its own vertical degree of freedom.

The prescribed series compliance could not keep the contact alive because it has no
rail mass. `track_dynamics.kind = "local_compliant"` already gives each rail a
vertical (and lateral) DOF with `mass_z_kg`, `support.k_z_n_m` and `support.c_z_n_s_m`,
so the rail can carry inertia instead of dropping instantly.

Parameters (SDITT `Par_TrackSystem.m`, FT-Modal): pad kz = 25e6 N/m each, two pads per
wheel footprint -> 50e6 N/m; damping 20e3 each -> 40e3 N s/m; the effective rail mass
seen by one wheel is about 2 m of 60 kg/m rail -> 120 kg.
"""

from __future__ import annotations

import json
import pathlib
import sys

BASE = pathlib.Path(__file__).resolve().parent
REFERENCE = BASE / "case_frog_N_strip05.json"
TEMPLATE = BASE / "case_Z_local_rail.json"


def main() -> int:
    raw = json.loads(REFERENCE.read_text(encoding="utf-8"))
    raw["case_id"] = "crh380a_m_z_local_rail"
    raw.pop("support_compliance", None)
    raw["track_dynamics"] = {"kind": "local_compliant"}
    for template in raw["rail_templates"]:
        template["mass_y_kg"] = 120.0
        template["mass_z_kg"] = 120.0
        template["support"] = {"k_y_n_m": 30e6, "c_y_n_s_m": 20e3,
                               "k_z_n_m": 50e6, "c_z_n_s_m": 40e3}
    TEMPLATE.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(TEMPLATE.name, TEMPLATE.stat().st_size, "bytes")
    print("track_dynamics:", raw["track_dynamics"])
    for template in raw["rail_templates"]:
        print(" template", template["id"], "bodies",
              len(template.get("bodies", [])), "support", template["support"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
