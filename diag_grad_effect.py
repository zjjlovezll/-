import sys, numpy as np
sys.path.insert(0,"src")
import velch.contact as C
from velch.vehicle import load_vehicle_case

case = load_vehicle_case(r"validation/crh380a_m/case_B_turnout.json")
rail = [r for r in case.rails if r.id == "axle1_right"][0]
wheel = {w.id: w for w in case.wheels}[rail.wheel_id]
print("rail", rail.id, "wheel", wheel.id, "lat", wheel.lateral_offset_m)
H = case.vehicle.wheel_center_height_m

def pen_at(x, qz=-0.00046, qy=0.0):
    s = rail.profiles.sample(x, 1)
    g = C.find_graph_contact(wheel.profile, s, wheel_y_m=qy, wheel_z_m=H+qz,
                             wheel_roll_rad=0.0, wheel_lateral_offset_m=wheel.lateral_offset_m,
                             rail_y_m=0.0, rail_z_m=0.0)
    return 0.0 if g is None else g.penetration_m

new = C._grid_slope
def numpy_like(z, x):
    return np.gradient(z, x, edge_order=1)

xs = np.arange(13.5, 130.0, 0.05)
C._grid_slope = new
base = np.array([pen_at(float(x)) for x in xs])
C._grid_slope = numpy_like
alt  = np.array([pen_at(float(x)) for x in xs])
C._grid_slope = new

d = alt - base
print("baseline mm: min %.4f mean %.4f max %.4f  gaps %d" % (base.min()*1e3, base.mean()*1e3, base.max()*1e3, int((base<5e-5).sum())))
print("numpy    mm: min %.4f mean %.4f max %.4f  gaps %d" % (alt.min()*1e3, alt.mean()*1e3, alt.max()*1e3, int((alt<5e-5).sum())))
print("|diff| mm: max %.4f mean %.5f count>0.01mm %d" % (np.abs(d).max()*1e3, np.abs(d).mean()*1e3, int((np.abs(d)>1e-5).sum())))
i = int(np.argmax(np.abs(d)))
print("worst x=%.2f base=%.4f numpy=%.4f mm" % (xs[i], base[i]*1e3, alt[i]*1e3))
