"""Repair pass 5: the left rail must follow the route too.

Symptom that exposed this: with only the right rail shifted, the static equilibrium reported one patch
at 0 N and the other at 119 277 N -- the left wheel had been carried 0.13..0.17 m outboard of a left
rail that stayed on the through centreline.  Both rails need the same path offset as the wheels.
"""

from __future__ import annotations

from pathlib import Path

path = Path(__file__).with_name("build_diverging_case.py")
text = path.read_text(encoding="utf-8")

anchor = "    template_case = dict(template)"
insert = '''    left_index = next((i for i, rail in enumerate(template["rail_templates"])
                       if rail.get("stations")), 0)
    left_profile = dict(template["rail_templates"][left_index]["stations"][0]["profile"])
    left_entries = []
    for index in range(count + 1):
        station_m = lo + index * STEP_M
        spec = dict(left_profile)
        spec["y_offset_m"] = round(-RAIL_HALF_GAUGE_M + route_offset_m(station_m), 9)
        left_entries.append({"s_m": round(station_m, 6), "id": f"lef{index:05d}", "profile": spec})

'''
if "left_entries = []" not in text:
    text = text.replace(anchor, insert + anchor, 1)

assign_anchor = '    rails[right_index]["stations"] = [entry[4] for entry in entries]'
if "rails[left_index][\"stations\"] = left_entries" not in text:
    text = text.replace(assign_anchor,
                        '    rails[left_index]["stations"] = left_entries\n' + assign_anchor, 1)

path.write_text(text, encoding="utf-8")
print("repaired pass 5: left rail follows the route as well")
