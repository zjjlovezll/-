import sys, csv, numpy as np
sys.path.insert(0,"src")
import velch.contact as C
from velch.vehicle import load_vehicle_case
case = load_vehicle_case(r"validation/crh380a_m/case_B_turnout.json")
cfg = case.vehicle
rail = [r for r in case.rails if r.id == "axle1_right"][0]
wheel = {w.id: w for w in case.wheels}[rail.wheel_id]
with open(r"validation/crh380a_m/out_B_1p2s_w2/history.csv", newline="", encoding="utf-8") as f:
    rd = csv.reader(f); h = next(rd); d = list(rd)
ix = {n: i for i, n in enumerate(h)}
f_r = np.array([float(r[ix["axle1_right_normal_n"]]) for r in d])
peak = int(np.argmax(f_r))
picks = sorted(set([peak, max(0,peak-20), min(len(d)-1,peak+20), int(np.argmax(f_r > 0))]))
for i in picks:
    r = d[i]
    x = float(r[ix["axle1_x_m"]]); y = float(r[ix["axle1_y_m"]]); z = float(r[ix["axle1_z_m"]])
    roll = float(r[ix["axle1_roll_rad"]])
    smp = rail.profiles.sample(x, 1)
    many = C.find_graph_contacts(wheel.profile, smp, wheel_y_m=y, wheel_z_m=cfg.wheel_center_height_m+z,
                                 wheel_roll_rad=roll, wheel_lateral_offset_m=wheel.lateral_offset_m,
                                 rail_y_m=0.0, rail_z_m=0.0, maximum_contacts=4)
    print("t=%.4f x=%7.3f F=%9.1f N  contacts=%d  %s" % (
        float(r[ix["time_s"]]), x, f_r[i], len(many),
        "; ".join("y=%.1f pen=%.3f mm" % (g.y_m*1e3, g.penetration_m*1e3) for g in many)))
