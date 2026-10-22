import sys, csv, numpy as np
from pathlib import Path
sys.path.insert(0,"src")
from velch.vehicle import load_vehicle_case
from velch.contact import find_graph_contact
base = Path(r"validation\crh380a_m")
case = load_vehicle_case(base/"case_B_turnout.json")
rail = [r for r in case.rails if r.id == "axle1_right"][0]
wheel = [w for w in case.wheels if w.id == "R"][0]
H = case.vehicle.wheel_center_height_m
rows=list(csv.DictReader(open('validation/crh380a_m/out_B_1p2s_fast/history.csv',encoding='utf-8')))
cell=lambda n,i: float(rows[i][n])
sel=[i for i in range(len(rows)) if 80.0 <= cell('axle1_x_m',i) <= 84.0]
print('samples in 80..84 m:',len(sel))
worst=None
for i in sel:
    x=cell('axle1_x_m',i); yaw=cell('axle1_yaw_rad',i)
    g=find_graph_contact(wheel.profile, rail.profiles.sample(x,1),
        wheel_y_m=cell('axle1_y_m',i), wheel_z_m=H+cell('axle1_z_m',i),
        wheel_roll_rad=cell('axle1_roll_rad',i), wheel_lateral_offset_m=wheel.lateral_offset_m,
        rail_y_m=0.0, rail_z_m=0.0)
    pen_rec=cell('axle1_right_penetration_m',i); act=cell('axle1_right_active',i)
    pen=np.nan if g is None else g.penetration_m
    if worst is None or abs((0 if g is None else pen)-pen_rec)>worst[0]:
        worst=(abs((0 if g is None else pen)-pen_rec), i, x, pen, pen_rec)
    if abs(cell('axle1_right_normal_n',i))>2e5 or i in sel[-6:]:
        print(' i=%4d x=%7.3f y=%+8.4f z=%+8.4f roll=%+9.6f | pen_rec=%8.4f pen_calc=%8.4f act=%.0f' % (
        i,x,cell('axle1_y_m',i)*1e3,cell('axle1_z_m',i)*1e3,cell('axle1_roll_rad',i),pen_rec*1e3,(np.nan if g is None else pen*1e3),act))
print('\nworst discrepancy: dpen=%.4f mm at i=%d x=%.3f calc=%.4f rec=%.4f' % (worst[0]*1e3,worst[1],worst[2],(worst[3] if worst[3]==worst[3] else float('nan'))*1e3,worst[4]*1e3))
