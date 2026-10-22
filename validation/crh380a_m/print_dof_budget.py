"""Print the DOF budget of representative cases, to keep ONBOARDING's table honest."""

from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
for name in ("case_full12_cap05.json", "case_AB_slab3.json", "case_Z_local_rail.json",
             "case_frog_strip_soft.json"):
    path = BASE / name
    if not path.exists():
        print(f"{name:<28} missing")
        continue
    case = json.loads(path.read_text(encoding="utf-8"))
    dynamics = case.get("track_dynamics") or {}
    layers = dynamics.get("layers") or []
    print(f"{name:<28} kind={dynamics.get('kind')!s:<16} layers={len(layers)} "
          f"templates={len(case['rail_templates'])} q={len(case['initial_state']['q'])}")
