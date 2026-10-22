import sys, numpy as np
from pathlib import Path
sys.path.insert(0,"src")
from velch.vehicle import load_vehicle_case
from velch.contact import find_graph_contact
from velch.profiles import graph_from_points, ProfileSample
base = Path(r"validation\crh380a_m")
case = load_vehicle_case(base/"case_B_turnout.json")
rail = [r for r in case.rails if r.id == "axle1_right"][0]
wheel = [w for w in case.wheels if w.id == "R"][0]
H = case.vehicle.wheel_center_height_m; QZ=-0.00046

def bands_of(y,z,theight=0.015):
    zmax=z.max(); keep=z>zmax-theight
    out=[]; i=0
    while i<len(keep):
        if keep[i]:
            j=i
            while j+1<len(keep) and keep[j+1]: j+=1
            if (y[j]-y[i])>0.010: out.append((i,j))
            i=j+1
        else: i+=1
    return out

def probe(x, split):
    smp=rail.profiles.sample(float(x),1); gp=smp.profile; y=gp.y_m; z=gp.z_m
    if not split:
        g=find_graph_contact(wheel.profile,smp,wheel_y_m=0.0,wheel_z_m=H+QZ,wheel_roll_rad=0.0,
            wheel_lateral_offset_m=wheel.lateral_offset_m,rail_y_m=0.0,rail_z_m=0.0)
        return (np.nan if g is None else g.penetration_m*1e3), (np.nan if g is None else g.y_m*1e3), 1
    best=(np.nan,np.nan); nb=0
    for i,j in bands_of(y,z):
        nb+=1
        sub=graph_from_points(np.column_stack([y[i:j+1],z[i:j+1]]),source_sha256='x',source='x',surface='rail_top')
        ps=ProfileSample(profile=sub,dz_ds=np.zeros_like(sub.y_m),lower_s_m=smp.lower_s_m,upper_s_m=smp.upper_s_m,selected_ids=smp.selected_ids)
        g=find_graph_contact(wheel.profile,ps,wheel_y_m=0.0,wheel_z_m=H+QZ,wheel_roll_rad=0.0,
            wheel_lateral_offset_m=wheel.lateral_offset_m,rail_y_m=0.0,rail_z_m=0.0)
        if g is not None and (np.isnan(best[0]) or g.penetration_m*1e3>best[0]): best=(g.penetration_m*1e3,g.y_m*1e3)
    return best[0],best[1],nb

for lo,hi,tag in ((51.0,56.6,'51-56 m'),(79.0,80.2,'79-80 m'),(80.2,80.7,'80.2-80.7 m'),(82.0,84.0,'82-84 m')):
    xs=np.arange(lo,hi,0.1)
    A=[probe(x,False) for x in xs]; B=[probe(x,True) for x in xs]
    pa=np.array([a[0] for a in A]); pb=np.array([b[0] for b in B])
    print('%-11s 单面: pen %.4f..%.4f mm, 无接触 %2d/%d | 分轨: pen %.4f..%.4f mm, 无接触 %2d/%d' % (
        tag,np.nanmin(pa),np.nanmax(pa),int((pa<0.05).sum()),len(xs),np.nanmin(pb),np.nanmax(pb),int((pb<0.05).sum()),len(xs)))
print('')
print('子轨数量样本 (x, 子轨数):', [(round(float(x),1), probe(x,True)[2]) for x in (52.0,53.0,54.0,80.4,80.6,82.4,84.0)])
