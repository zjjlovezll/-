import sys, numpy as np
from pathlib import Path
sys.path.insert(0,"src")
from velch.vehicle import load_vehicle_case
from velch.contact import find_graph_contact
from velch.profiles import ProfileSample
base = Path(r"validation\crh380a_m")
case = load_vehicle_case(base/"case_B_turnout.json")
rail = [r for r in case.rails if r.id == "axle1_right"][0]
wheel = [w for w in case.wheels if w.id == "R"][0]
H=case.vehicle.wheel_center_height_m; QZ=-0.00046
prof=rail.profiles; S=prof._stations
def pen_of(gp):
    ps=ProfileSample(profile=gp,dz_ds=np.zeros_like(gp.y_m),lower_s_m=0.0,upper_s_m=0.0,selected_ids=())
    g=find_graph_contact(wheel.profile,ps,wheel_y_m=0.0,wheel_z_m=H+QZ,wheel_roll_rad=0.0,
        wheel_lateral_offset_m=wheel.lateral_offset_m,rail_y_m=0.0,rail_z_m=0.0)
    return np.nan if g is None else g.penetration_m*1e3
xs=np.arange(51.0,56.61,0.2)
A=[];B=[]
for x in xs:
    A.append(pen_of(rail.profiles.sample(float(x),1).profile))
    i=int(np.argmin(np.abs(np.array(S)-x)))
    best=np.nan
    for j in {max(0,i-1),i,min(len(S)-1,i+1)}:
        p=pen_of(prof._groups[S[j]][0].profile)
        if not np.isnan(p) and (np.isnan(best) or p>best): best=p
    B.append(best)
A=np.array(A);B=np.array(B)
print('插值     pen %.4f..%.4f  无接触 %d/%d mean %.4f'%(np.nanmin(A),np.nanmax(A),int((A<0.05).sum()),len(A),np.nanmean(A)))
print('邻近站   pen %.4f..%.4f  无接触 %d/%d mean %.4f'%(np.nanmin(B),np.nanmax(B),int((B<0.05).sum()),len(B),np.nanmean(B)))
print('站距 (51..57):', ['%.3f'%(S[i+1]-S[i]) for i in range(len(S)-1) if 51<=S[i]<=57][:12])
