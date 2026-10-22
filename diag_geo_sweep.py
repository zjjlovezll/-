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
QZ=-0.00046
xs=np.arange(13.5,130.001,0.05)
pen=np.full(len(xs),np.nan); yc=np.full(len(xs),np.nan); ed=np.zeros(len(xs),bool)
for k,x in enumerate(xs):
    smp=rail.profiles.sample(float(x),1)
    g=find_graph_contact(wheel.profile,smp,wheel_y_m=0.0,wheel_z_m=H+QZ,wheel_roll_rad=0.0,
        wheel_lateral_offset_m=wheel.lateral_offset_m,rail_y_m=0.0,rail_z_m=0.0)
    if g is not None:
        pen[k]=g.penetration_m*1e3; yc[k]=g.y_m*1e3; ed[k]=g.edge_limited
print('扫掠 %d 个里程 (13.5..130 m, 0.05 m 步长), 固定姿态 qz=%.2f mm roll=0' % (len(xs),QZ*1e3))
v=pen[~np.isnan(pen)]
print('pen: min %.4f max %.4f mean %.4f mm' % (v.min(),v.max(),v.mean()))
print('pen<0.05mm(无接触) 里程数 %d (%.1f%%); pen>0.4mm 里程数 %d; pen>0.6mm %d' % (
    int((v<0.05).sum()),100*(v<0.05).mean(),int((v>0.4).sum()),int((v>0.6).sum())))
print('edge_limited 里程数 %d' % int(ed.sum()))
print('contact y: min %.2f max %.2f mm' % (np.nanmin(yc),np.nanmax(yc)))
print('')
print('-- pen>0.4mm 的区段：')
m=(pen>0.4)&(~np.isnan(pen))
if m.any():
    idx=np.where(m)[0]; br=np.split(idx,np.where(np.diff(idx)>1)[0]+1)
    for b in br[:15]:
        print('   x %.3f..%.3f m  pen_max %.4f mm  y_c=%.2f' % (xs[b[0]],xs[b[-1]],np.nanmax(pen[b]),yc[b[int(np.nanargmax(pen[b]))]]))
print('')
print('-- pen<0.05mm（失去接触）的区段：')
m2=(pen<0.05)&(~np.isnan(pen))
if m2.any():
    idx=np.where(m2)[0]; br=np.split(idx,np.where(np.diff(idx)>1)[0]+1)
    print('   共 %d 段, 总长 %.2f m' % (len(br),float(m2.sum())*0.05))
    for b in br[:15]:
        print('   x %.3f..%.3f m (长 %.2f m)' % (xs[b[0]],xs[b[-1]],(xs[b[-1]]-xs[b[0]])+0.05))
