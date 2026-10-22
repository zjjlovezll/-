"""Restore the path-consistent wiring: rails carry the route offset, the wheel follows the same offset.

Both must move together.  With only the rail shifted, a 5 mm station list at 61 m put the right rail
62 mm inboard and the static equilibrium failed ("hung-bogie branch ... 0 N while the heaviest carries
119222.7 N"); with only the wheel shifted, the wheel leaves the rail.  Together they cancel in the rail
reference frame, and the route's curvature enters through the creepage term (path slope).
"""

from __future__ import annotations

from pathlib import Path

builder = Path("validation/crh380a_m/build_diverging_case.py")
text = builder.read_text(encoding="utf-8")
old = "        known.append((station_m, RAIL_HALF_GAUGE_M - centre / 1000.0))"
new = "        known.append((station_m, RAIL_HALF_GAUGE_M + path_m - centre / 1000.0))"
if old in text:
    text = text.replace(old, new, 1)
    builder.write_text(text, encoding="utf-8")
    print("builder: placement includes the route offset")

solver = Path("src/velch/vehicle_solver.py")
code = solver.read_text(encoding="utf-8")
old_offset = ("                wheel_roll_rad=float(q[wh + 2]), "
              "wheel_lateral_offset_m=wheel.lateral_offset_m,")
new_offset = ("                wheel_roll_rad=float(q[wh + 2]),\n"
              "                wheel_lateral_offset_m=wheel.lateral_offset_m + lateral_extra,")
if old_offset in code:
    code = code.replace(old_offset, new_offset, 1)

old_rate = ("        lateral_rate = path.lateral_velocity_m_s(x, cfg.travel_speed_m_s) "
            "if path is not None else 0.0")
new_rate = ("        lateral_extra = path.at(x) if path is not None else 0.0\n"
            "        lateral_rate = path.lateral_velocity_m_s(x, cfg.travel_speed_m_s) "
            "if path is not None else 0.0")
if old_rate in code and "lateral_extra = path.at(x)" not in code:
    code = code.replace(old_rate, new_rate, 1)
solver.write_text(code, encoding="utf-8")
print("solver: wheel offset = own offset + path.at(x); lateral rate = speed * path slope")
