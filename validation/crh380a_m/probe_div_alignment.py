"""Why can't eight patches seat?  Print, for every rail at t = 0, the lateral bands.

For each axle the rail's absolute y band comes from the sampled profile (which already carries the
case's ``y_offset_m``); the wheel's comes from its own lateral offset plus the path offset at that
station.  A rail whose band does not overlap the wheel's cannot carry load, and the equilibrium then
fails with "the lightest contact patch carries only 0 N".
"""

from __future__ import annotations

import sys

import numpy as np

from velch.vehicle import load_vehicle_case

case = load_vehicle_case(sys.argv[1])
cfg = case.vehicle
direction = 1 if cfg.travel_speed_m_s >= 0 else -1
q = np.asarray(case.initial_q, dtype=float)
path = case.path

print(f"case {case.case_id}  x_start {case.run.x_start_m} m  path {path.summary() if path else 'none'}")
print(f"{'rail':<16}{'x_m':>8}{'path_mm':>9}{'rail y lo':>11}{'rail y hi':>11}"
      f"{'wheel lo':>10}{'wheel hi':>10}{'overlap':>9}")
for rail in case.rails:
    x = case.run.x_start_m + cfg.axle_offsets_m[rail.axle_index]
    sample = next(iter(rail.contact_bodies)).series.sample(x, direction)
    rail_y = np.asarray(sample.profile.y_m, dtype=float)
    offset = path.at(x) if path is not None else 0.0
    wheel = next(w for w in case.wheels if w.id == rail.wheel_id)
    wheel_y = np.asarray(wheel.profile.y_m, dtype=float) + wheel.lateral_offset_m + offset
    overlap = min(rail_y.max(), wheel_y.max()) - max(rail_y.min(), wheel_y.min())
    print(f"{rail.id:<16}{x:8.2f}{offset * 1e3:9.2f}{rail_y.min() * 1e3:11.2f}"
          f"{rail_y.max() * 1e3:11.2f}{wheel_y.min() * 1e3:10.2f}{wheel_y.max() * 1e3:10.2f}"
          f"{overlap * 1e3:9.2f}")

print("\npath at each axle station:")
for axle in range(4):
    x = case.run.x_start_m + cfg.axle_offsets_m[axle]
    print(f"  axle{axle + 1} x={x:7.2f} m  path={path.at(x) * 1e3:+9.3f} mm  "
          f"slope={path.slope_at(x):+.6f}")
