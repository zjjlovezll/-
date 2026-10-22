import sys, numpy as np, csv
sys.path.insert(0,"src")
import velch.contact as C
from velch.vehicle import load_vehicle_case

case = load_vehicle_case(r"validation/crh380a_m/case_B_turnout.json")
cfg = case.vehicle
rail = [r for r in case.rails if r.id == "axle1_left"][0]
wheel = {w.id: w for w in case.wheels}[rail.wheel_id]

with open(r"validation/crh380a_m/out_B_1p2s_fast/history.csv", newline="", encoding="utf-8") as f:
    rd = csv.reader(f); hdr = next(rd); rows = [r for r in rd]
ix = {n: i for i, n in enumerate(hdr)}
t_target = (64.8650352 - 13.5 - 10.0) / cfg.travel_speed_m_s
row = min(rows, key=lambda r: abs(float(r[ix["time_s"]]) - t_target))
t = float(row[ix["time_s"]]); x = float(row[ix["axle1_x_m"]])
y = float(row[ix["axle1_y_m"]]); z = float(row[ix["axle1_z_m"]]); roll = float(row[ix["axle1_roll_rad"]])
print("state t=%.6f x=%.4f y=%.6f mm z=%.6f mm roll=%.6f mrad" % (t, x, y*1e3, z*1e3, roll*1e3))

new = C._grid_slope
def numpy_like(z_, x_):
    return np.gradient(z_, x_, edge_order=1)

s = rail.profiles.sample(x, 1)
for tag, fn in (("simple-centred", new), ("numpy-weighted", numpy_like)):
    C._grid_slope = fn
    g = C.find_graph_contact(wheel.profile, s, wheel_y_m=y, wheel_z_m=cfg.wheel_center_height_m+z,
                             wheel_roll_rad=roll, wheel_lateral_offset_m=wheel.lateral_offset_m,
                             rail_y_m=0.0, rail_z_m=0.0)
    if g is None:
        print(tag, "no contact"); continue
    print("%-16s y=%.3f mm pen=%.6f mm slope=%+.4f normal=(%+.4f,%.4f) edge=%s"
          % (tag, g.y_m*1e3, g.penetration_m*1e3, g.normal_y/g.normal_z, g.normal_y, g.normal_z, g.edge_limited))
C._grid_slope = new
