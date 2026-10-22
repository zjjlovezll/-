import sys, numpy as np
sys.path.insert(0,"src")
import velch.contact as C
from velch.vehicle import load_vehicle_case

case = load_vehicle_case(r"validation/crh380a_m/case_B_turnout.json")
cfg = case.vehicle
rail = [r for r in case.rails if r.id == "axle1_right"][0]
wheel = {w.id: w for w in case.wheels}[rail.wheel_id]

def run(xs, half, qz=-0.00046, qy=0.0):
    out = []; prev = None
    for x in xs:
        s = rail.profiles.sample(float(x), 1)
        g = C.find_graph_contact(wheel.profile, s, wheel_y_m=qy, wheel_z_m=cfg.wheel_center_height_m+qz,
                                 wheel_roll_rad=0.0, wheel_lateral_offset_m=wheel.lateral_offset_m,
                                 rail_y_m=0.0, rail_z_m=0.0,
                                 search_half_width_m=half, previous_y_m=prev)
        out.append(None if g is None else (g.y_m, g.penetration_m))
        prev = None if g is None else g.y_m
    return out

for lo, hi in ((78.0, 82.0), (49.0, 58.0), (13.5, 130.0)):
    xs = np.arange(lo, hi, 0.05)
    g = run(xs, None); w = run(xs, 0.002)
    dy, dp, miss = 0.0, 0.0, 0
    for a, b in zip(g, w):
        if a is None or b is None:
            miss += (a is None) != (b is None); continue
        dy = max(dy, abs(a[0]-b[0])); dp = max(dp, abs(a[1]-b[1]))
    print("x %6.1f..%-6.1f n=%4d  max|dy| %.9f mm  max|dpen| %.9f mm  none-mismatch %d"
          % (lo, hi, xs.size, dy*1e3, dp*1e3, miss))
