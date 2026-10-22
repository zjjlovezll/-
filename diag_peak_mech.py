import sys, numpy as np
from pathlib import Path
sys.path.insert(0,"src")
from velch.vehicle import load_vehicle_case
from velch.contact import find_graph_contact
base = Path(r"validation\crh380a_m")
case = load_vehicle_case(base/"case_B_turnout.json")
rail = [r for r in case.rails if r.id == "axle1_right"][0]
wheel = [w for w in case.wheels if w.id == "R"][0]
H = case.vehicle.wheel_center_height_m
wy = wheel.profile.y_m + wheel.lateral_offset_m
wz = wheel.profile.z_m
print("H=%.4f off=%.4f" % (H, wheel.lateral_offset_m))
print("wheel abs y %.1f..%.1f mm ; z %.3f..%.3f mm" % (wy.min()*1e3, wy.max()*1e3, wz.min()*1e3, wz.max()*1e3))
def bands(y,z,thr):
    b=z>thr; out=[]; i=0
    while i<len(b):
        if b[i]:
            j=i
            while j+1<len(b) and b[j+1]: j+=1
            out.append((y[i]*1e3,y[j]*1e3)); i=j+1
        else: i+=1
    return out
print("\n   x      qz[mm]  pen[mm]  y_c[mm]   edge   n_top  top_spans(mm)")
for x,qz in ((79.9,-0.00046),(80.3,-0.00046),(80.9,-0.00046),(81.5,-0.00046),(82.0,-0.00046),
             (82.368,-0.000823),(82.368,-0.00046),(82.6,-0.00046),(84.0,-0.00046)):
    smp = rail.profiles.sample(x,1)
    gp = smp.profile
    y=gp.y_m; z=gp.z_m
    g = find_graph_contact(wheel.profile, smp,
                           wheel_y_m=-0.000726 if (x==82.368 and qz==-0.000823) else 0.0,
                           wheel_z_m=H+qz, wheel_roll_rad=0.0,
                           wheel_lateral_offset_m=wheel.lateral_offset_m, rail_y_m=0.0, rail_z_m=0.0)
    bs=bands(y,z,z.max()-0.005)
    tag=["%.1f..%.1f"%(a,b) for a,b in bs]
    if g is None:
        print(" %7.3f %+8.3f   None             %2d  %s" % (x,qz*1e3,len(bs),tag))
    else:
        print(" %7.3f %+8.3f %+8.4f %9.3f  %-5s  %2d  %s" % (x,qz*1e3,g.penetration_m*1e3,g.y_m*1e3,str(g.edge_limited),len(bs),tag))
for x,qz in ((80.9,-0.00046),(82.368,-0.000823)):
    smp=rail.profiles.sample(x,1); gp=smp.profile; y=gp.y_m; z=gp.z_m
    print("\n--- x=%.3f  rail %d pts  y %.1f..%.1f mm  z %.3f..%.3f mm" % (x,len(y),y.min()*1e3,y.max()*1e3,z.min()*1e3,z.max()*1e3))
    lo=max(wy.min(),y.min()); hi=min(wy.max(),y.max())
    for t in np.linspace(lo,hi,17):
        rz=np.interp(t,y,z); wzz=np.interp(t,wy,wz)+H+qz
        print("   y=%8.2f  rail_z=%+9.3f  wheel_z=%+9.3f  depth=%+8.3f mm" % (t*1e3,rz*1e3,wzz*1e3,(rz-wzz)*1e3))
