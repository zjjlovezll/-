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
smp=rail.profiles.sample(82.368,1)
for roll in (0.0,-0.000495,-0.002):
    g=find_graph_contact(wheel.profile,smp,wheel_y_m=-0.000726,wheel_z_m=H-0.0008233,
        wheel_roll_rad=roll,wheel_lateral_offset_m=wheel.lateral_offset_m,rail_y_m=0.0,rail_z_m=0.0)
    print('roll=%+9.6f  pen=%8.4f mm  y_c=%9.3f mm' % (roll,g.penetration_m*1e3,g.y_m*1e3))
# 逐 y 深度，roll=-0.000495
wy=wheel.profile.y_m+wheel.lateral_offset_m; wz=wheel.profile.z_m
gp=smp.profile; y=gp.y_m; z=gp.z_m
for roll in (0.0,-0.000495):
    s=np.sin(roll); c=np.cos(roll)
    wyy=0.0+ c*wy - s*wz; wzz=(H-0.0008233)+ s*wy + c*wz
    lo=max(wyy.min(),y.min()); hi=min(wyy.max(),y.max())
    t=np.linspace(lo,hi,200001)
    d=np.interp(t,y,z)-np.interp(t,wyy,wzz)
    i=int(np.argmax(d))
    print('roll=%+9.6f  argmax depth=%9.4f mm at y=%9.3f mm' % (roll,d[i]*1e3,t[i]*1e3))
