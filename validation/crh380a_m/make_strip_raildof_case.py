"""Strip contact + rail vertical DOF on the frog window.

The two capabilities exist separately and have never been combined on this window:
`case_frog_N_strip05` has `normal_policy = strip_integral` on a rigid track, and
`case_Z_local_rail` has the rail DOF (kz=50e6, cz=20e3) with single-point Hertz.

`SPECTRUM_SOURCE_2026-10-21.md` predicts that the 10 dropped samples and the broadband
150-250 Hz energy both come from the contact losses, so combining them should clear the
losses without touching the contact law.
"""

from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_frog_N_strip05.json"
TRACK_FROM = BASE / "case_Z_local_rail.json"

raw = json.loads(SOURCE.read_text(encoding="utf-8"))
donor = json.loads(TRACK_FROM.read_text(encoding="utf-8"))

raw["track_dynamics"] = dict(donor["track_dynamics"])
# The rail DOF adds 2 states per rail; the frog case has 8 rails, so 35 -> 51.
extra = len(donor["initial_state"]["q"]) - len(raw["initial_state"]["q"])
if extra <= 0:
    raise SystemExit(f"donor is not larger: extra={extra}")
raw["initial_state"]["q"] = list(raw["initial_state"]["q"]) + [0.0] * extra
if isinstance(raw["initial_state"].get("v"), list):
    raw["initial_state"]["v"] = list(raw["initial_state"]["v"]) + [0.0] * extra
raw["case_id"] = "frog_strip_raildof"
raw["purpose_detail"] = (raw.get("purpose_detail", "")
                         + " | strip_integral + rail vertical DOF (kz=50e6, cz=20e3)")

path = BASE / "case_frog_strip_raildof.json"
path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
print("wrote", path.name, "q length", len(raw["initial_state"]["q"]))
