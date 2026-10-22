import numpy as np, sys
sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\src")
from velch.vehicle import load_vehicle_case
from velch.contact import find_graph_contact
case = load_vehicle_case(r"F:\ai道岔状态反演辨识\Velch\validation\crh380a_m\case_C_frog.json")
rail = [r for r in case.rails if r.id.endswith("right")][0]
wheel = case.wheels[1]
zc = 0.430 - 0.4628e-3
print(f"wheel ref offset {wheel.lateral_offset_m*1e3:.2f} mm  bodies {[b.id for b in rail.contact_bodies]}")
for s in (79.90, 79.97, 80.05, 80.20, 80.35, 80.50, 80.70, 80.91, 81.00, 81.29, 81.67, 82.05, 82.37):
    parts = []
    for b in rail.contact_bodies:
        if not b.active_at(s): continue
        smp = b.series.sample(s, 1)
        ry = np.asarray(smp.profile.y_m); rz = np.asarray(smp.profile.z_m)
        g = find_graph_contact(wheel.profile, smp, wheel_y_m=0.0, wheel_z_m=zc, wheel_roll_rad=0.0,
                               wheel_lateral_offset_m=wheel.lateral_offset_m,
                               rail_y_m=ry, rail_z_m=rz)
        if g is None: parts.append(f"{b.id}: none")
        else: parts.append(f"{b.id}: y={g.y_m*1e3:7.2f} pen={g.penetration_m*1e3:+7.4f} edge={g.edge_limited}")
    print(f"s={s:7.3f}  " + " | ".join(parts))
