"""Repair pass 2: target the right rail template and drop the route offset from the rail placement.

Two corrections over the first version of ``build_diverging_case.py``:

* ``rail_templates[0]`` is the **left** rail (its station profile carries ``y_offset_m = -0.753``), so
  the diverging stations belong on the template whose offset is positive.
* The case's path is expressed in the rail reference frame: the route's centreline offset is absorbed
  by the rail placement, so the placement must be the standard half-gauge minus the file's own band
  centre -- not plus the route offset (which would place the rail two metres away at the far end).
"""

from __future__ import annotations

from pathlib import Path

path = Path(__file__).with_name("build_diverging_case.py")
text = path.read_text(encoding="utf-8")

# 1. offset without the route term
old_known = "        known.append((station_m, RAIL_HALF_GAUGE_M + path_m - centre / 1000.0))"
new_known = ("        # The file's own band centre is removed so the running band lands on the standard\n"
             "        # half-gauge line: the case works in the rail reference frame, not the through frame.\n"
             "        known.append((station_m, RAIL_HALF_GAUGE_M - centre / 1000.0))")
if old_known in text:
    text = text.replace(old_known, new_known, 1)

# 2. pick the right rail template by the sign of its station offset
old_pick = '    rails = [dict(t) for t in template["rail_templates"]]\n    rails[0]["stations"] = [entry[4] for entry in entries]\n    rails[0].pop("bodies", None)'
new_pick = ('    rails = [dict(t) for t in template["rail_templates"]]\n'
            '    right_index = 0\n'
            '    for index, rail in enumerate(rails):\n'
            '        first = rail.get("stations") or []\n'
            '        offset = 0.0\n'
            '        if first:\n'
            '            offset = float(first[0].get("profile", {}).get("y_offset_m", 0.0))\n'
            '        if offset > 0:\n'
            '            right_index = index\n'
            '            break\n'
            '    rails[right_index]["stations"] = [entry[4] for entry in entries]\n'
            '    rails[right_index].pop("bodies", None)\n'
            '    print(f"  diverging stations written to rail_templates[{right_index}]")\n'
            '    other = [i for i in range(len(rails)) if i != right_index]\n'
            '    for index in other:\n'
            '        rails[index].pop("bodies", None)')
if old_pick in text:
    text = text.replace(old_pick, new_pick, 1)

path.write_text(text, encoding="utf-8")
print("repaired pass 2:", path.name)
