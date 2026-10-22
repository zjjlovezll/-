import sys, numpy as np
sys.path.insert(0,"src")
import velch.contact as C
from velch.vehicle import load_vehicle_case
case = load_vehicle_case(r"validation/crh380a_m/case_B_turnout.json")
cfg = case.vehicle
rail = [r for r in case.rails if r.id == "axle1_right"][0]
wheel = {w.id: w for w in case.wheels}[rail.wheel_id]
for x in (53.606, 54.563, 55.280, 60.0, 80.4, 82.4):
    smp = rail.profiles.sample(x, 1)
    many = C.find_graph_contacts(wheel.profile, smp, wheel_y_m=0.0,
                                 wheel_z_m=cfg.wheel_center_height_m-0.00046, wheel_roll_rad=0.0,
                                 wheel_lateral_offset_m=wheel.lateral_offset_m,
                                 rail_y_m=0.0, rail_z_m=0.0, maximum_contacts=3)
    one = C.find_graph_contact(wheel.profile, smp, wheel_y_m=0.0,
                               wheel_z_m=cfg.wheel_center_height_m-0.00046, wheel_roll_rad=0.0,
                               wheel_lateral_offset_m=wheel.lateral_offset_m,
                               rail_y_m=0.0, rail_z_m=0.0)
    print("x=%-7.3f contacts=%d  %s | single y=%.3f pen=%.4f mm" % (
        x, len(many),
        "; ".join("y=%.1f pen=%.4f slope=%+.2f" % (g.y_m*1e3, g.penetration_m*1e3, g.normal_y/g.normal_z) for g in many),
        one.y_m*1e3 if one else float("nan"), one.penetration_m*1e3 if one else 0.0))
