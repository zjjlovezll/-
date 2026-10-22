import sys, numpy as np
from pathlib import Path
sys.path.insert(0,"src")
from velch.vehicle import load_vehicle_case
base = Path(r"validation\crh380a_m")
case = load_vehicle_case(base/"case_B_turnout.json")
rail = [r for r in case.rails if r.id == "axle1_right"][0]
wheel = [w for w in case.wheels if w.id == "R"][0]
H=case.vehicle.wheel_center_height_m; QZ=-0.00046
wy=wheel.profile.y_m+wheel.lateral_offset_m; wz=wheel.profile.z_m
for x in (52.0,53.0,54.0,55.0,79.9,80.4):
    smp=rail.profiles.sample(x,1); gp=smp.profile; y=gp.y_m; z=gp.z_m
    top=z.max(); ty=y[int(z.argmax())]
    lo=max(wy.min(),y.min()); hi=min(wy.max(),y.max())
    t=np.linspace(lo,hi,4001)
    d=np.interp(t,y,z)-(np.interp(t,wy,wz)+H+QZ)
    i=int(np.argmax(d))
    # 轨顶最高点处的轮面高度
    wr=np.interp(ty,wy,wz)+H+QZ
    print('x=%6.2f  rail_top=(%.2f, %+.4f mm)  轮在该处=%+.4f mm  → %s | 最大深度 %+.4f mm @ y=%.2f | 轮滚动圆处轨面 %+.4f 轮面 %+.4f' % (
        x,ty*1e3,top*1e3,wr*1e3,'接触' if (top-wr)<0 else '间隙 %.4f mm'%(top-wr)*1e3 if False else ('接触' if top-wr<0 else '悬空 %.4f mm'%((top-wr)*1e3)),
        d[i]*1e3,t[i]*1e3,np.interp(0.7465,y,z)*1e3,(np.interp(0.7465,wy,wz)+H+QZ)*1e3))
