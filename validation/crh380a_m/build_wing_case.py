"""Add a continuous wing-rail body over the frog closure section (scheme B).

Rationale
---------
In `case_C_bodies.json` the right rail is split into `main` (the merged
cross-section as extracted from the model's PRRs) and `point` (the point rail
narrowing band).  Across 79.1-80.9 m the *merged* `main` body has no continuous
crown inside the running band: its z = 0 crest migrates laterally from ~760 to
~820 mm and the band 740-775 mm is left ~1.3 mm low.  The vehicle therefore loses
its support between 80.03 and 80.37 m and re-impacts at 82.37 m (600 kN).

A real 60TY1 wing rail is a continuous 60 kg/m head at the design height through
the closure section, with the point rail rising underneath it.  This script adds
exactly that: a third body `wing` whose stations reference the *same* flat-rail
profile (`Profile_Mileage_JBG.prr`) with the *same* loader transforms already
used for the approach track.  No geometry is invented - the wing rail through the
closure section is the approach rail continued, which is what the drawing says
("60TY1 wing rail", note 9.5).

Output: case_I_wing.json (velocity = 350 km/h, x_start unchanged from
case_C_bodies.json) plus a frog window case built separately.
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "case_C_bodies.json"
TARGET = HERE / "case_I_wing.json"

JBG = (
    "G:\\研究生\\动力学\\CRH380A_纯刚性模型\\database\\database"
    "\\wheel_rail_profiles\\Profile_Mileage_JBG.prr"
)
S_LO = 79.0000
S_HI = 80.9110


def main() -> None:
    case = json.loads(SOURCE.read_text(encoding="utf-8"))
    right = next(t for t in case["rail_templates"] if "bodies" in t)
    main_body = next(b for b in right["bodies"] if b["id"] == "main")
    if any(b["id"] == "wing" for b in right["bodies"]):
        raise SystemExit("wing body already present")

    mileages = sorted(
        st["s_m"] for st in main_body["stations"] if S_LO - 1e-9 <= st["s_m"] <= S_HI + 1e-9
    )
    if len(mileages) < 10:
        raise SystemExit(f"too few stations in window: {len(mileages)}")

    stations = [
        {
            "id": f"W{i:03d}",
            "s_m": float(s),
            "profile": {
                "file": JBG,
                "format": "prr",
                "units": "m",
                "y_sign": 1,
                "y_offset_m": 0.753,
                "z_sign": -1,
            },
        }
        for i, s in enumerate(mileages, start=1)
    ]
    wing = {"id": "wing", "s_lo_m": S_LO, "s_hi_m": S_HI, "stations": stations}
    right["bodies"].append(wing)

    case["case_id"] = "crh380a_m_turnout_350kmh_wing_1p2s"
    TARGET.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wing body: {len(stations)} stations, s {stations[0]['s_m']} .. {stations[-1]['s_m']}")
    print(f"bodies: {[b['id'] for b in right['bodies']]}")
    print(f"written {TARGET}")


if __name__ == "__main__":
    main()
