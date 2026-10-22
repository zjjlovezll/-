import sys, numpy as np, csv
sys.path.insert(0,"src")
import velch.contact as C
from velch.vehicle import load_vehicle_case

case = load_vehicle_case(r"validation/crh380a_m/case_win_global_x60.json")
cfg = case.vehicle
rail = [r for r in case.rails if r.id == "axle1_right"][0]
wheel = {w.id: w for w in case.wheels}[rail.wheel_id]
a = rail.axle_index + 1

with open(r"validation/crh380a_m/out_win_global_x60/history.csv", newline="", encoding="utf-8") as f:
    rd = csv.reader(f); hdr = next(rd); rows = [r for r in rd]
ix = {n: i for i, n in enumerate(hdr)}

def contact_at(row, half, prev):
    y = float(row[ix[f"axle{a}_y_m"]]); z = float(row[ix[f"axle{a}_z_m"]])
    roll = float(row[ix[f"axle{a}_roll_rad"]]); x = float(row[ix[f"axle{a}_x_m"]])
    s = rail.profiles.sample(x, 1)
    return C.find_graph_contact(wheel.profile, s, wheel_y_m=y,
                                wheel_z_m=cfg.wheel_center_height_m + z, wheel_roll_rad=roll,
                                wheel_lateral_offset_m=wheel.lateral_offset_m,
                                rail_y_m=0.0, rail_z_m=0.0,
                                search_half_width_m=half, previous_y_m=prev)

prev = None; worst_dy = worst_dpen = 0.0; n = 0; misses = 0
for r in rows:
    g = contact_at(r, None, None)
    if g is None:
        prev = None; continue
    w = contact_at(r, 0.002, prev)
    if w is None:
        misses += 1
    else:
        worst_dy = max(worst_dy, abs(w.y_m - g.y_m))
        worst_dpen = max(worst_dpen, abs(w.penetration_m - g.penetration_m))
        n += 1
    prev = g.y_m
print("contact samples %d / %d ; window returned None %d" % (n, len(rows), misses))
print("max |dy| windowed-vs-global at identical states : %.9f mm" % (worst_dy*1e3))
print("max |d penetration|                             : %.9f mm" % (worst_dpen*1e3))
