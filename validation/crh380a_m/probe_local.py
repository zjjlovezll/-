import sys
from pathlib import Path
sys.path.insert(0,"src")
from velch.vehicle import load_vehicle_case
from velch.contact import find_graph_contact
base = Path(r"validation\crh380a_m")
case = load_vehicle_case(base/"case_B_turnout.json")
rail = [r for r in case.rails if r.id == "axle1_right"][0]
wheel = [w for w in case.wheels if w.id == "R"][0]
H = case.vehicle.wheel_center_height_m
print(f"H={H}  wheel lateral_offset={wheel.lateral_offset_m}")
print("   x_m     qz[mm]   pen[mm]  contact_y[mm]  slope-ratio  edge")
for x, qz in ((13.5,-0.00020),(13.5,-0.00046),(60.0,-0.00046),(70.0,-0.00046),
              (80.0,-0.00046),(82.42,-0.00046),(82.42,-0.00060),(82.42,-0.00140),(84.0,-0.00046)):
    smp = rail.profiles.sample(x, 1)
    g = find_graph_contact(wheel.profile, smp, wheel_y_m=0.0, wheel_z_m=H+qz, wheel_roll_rad=0.0,
                           wheel_lateral_offset_m=wheel.lateral_offset_m, rail_y_m=0.0, rail_z_m=0.0)
    if g is None:
        print(f" {x:7.2f} {qz*1e3:+8.3f}   None"); continue
    print(f" {x:7.2f} {qz*1e3:+8.3f} {g.penetration_m*1e3:+8.4f} {g.y_m*1e3:12.3f} {g.normal_y/g.normal_z:+10.3f}  {g.edge_limited}")
