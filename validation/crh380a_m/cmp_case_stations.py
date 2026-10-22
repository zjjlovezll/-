"""Compare station tables and x_start across the diverging cases."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
NAMES = ("case_diverging_R1100.json", "case_diverging_multi.json", "case_diverging_clipped.json",
         "case_div_clip_diverging_clipped_0p05s.json", "case_Z_local_rail.json")

for name in NAMES:
    raw = json.loads((HERE / name).read_text(encoding="utf-8"))
    parts = [name, f"x_start={raw['run']['x_start_m']}"]
    for rail in raw["rail_templates"]:
        stations = rail.get("stations") or []
        if stations:
            parts.append(f"{rail['id']} stations {stations[0]['s_m']:.1f}..{stations[-1]['s_m']:.1f}"
                         f" n={len(stations)}")
        for body in rail.get("bodies") or []:
            values = [entry["s_m"] for entry in body["stations"]]
            parts.append(f"{rail['id']}/{body['id']} {min(values):.2f}..{max(values):.2f}")
    print(" | ".join(parts))
