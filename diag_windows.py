import csv, numpy as np
rows=list(csv.DictReader(open('validation/crh380a_m/out_B_1p2s_fast/history.csv',encoding='utf-8')))
c=lambda n: np.array([float(r[n]) for r in rows])
x=c('axle1_x_m'); z=c('axle1_z_m'); y=c('axle1_y_m'); roll=c('axle1_roll_rad')
Fr=c('axle1_right_normal_n'); Fl=c('axle1_left_normal_n')
for lo,hi,tag in ((13.5,20,'静态段'),(49,58,'51-56 m 无接触区'),(78,82,'79-80 台阶'),(82,98,'脱轨段'),(98,130,'后段')):
    m=(x>=lo)&(x<hi)
    if m.sum()==0: continue
    print('%-14s x[%6.1f,%6.1f) n=%3d  z=%+.3f..%+.3f mm  y=%+.3f..%+.3f mm  roll=%+.4f..%+.4f mrad  Fr=%7.0f..%8.0f (mean %7.0f)  脱轨%3d' % (
        tag,lo,hi,m.sum(),z[m].min()*1e3,z[m].max()*1e3,y[m].min()*1e3,y[m].max()*1e3,
        roll[m].min()*1e3,roll[m].max()*1e3,Fr[m].min(),Fr[m].max(),Fr[m].mean(),int((c('axle1_right_active')[m]==0).sum())))
print('')
print('z 全程范围 %+.3f..%+.3f mm ; 静态预载解 -0.463 mm' % (z.min()*1e3,z.max()*1e3))
print('roll 全程范围 %+.4f..%+.4f mrad ; 对应接触点竖移 %+.3f..%+.3f mm (力臂 0.7465 m)' % (roll.min()*1e3,roll.max()*1e3,roll.min()*0.7465*1e3,roll.max()*0.7465*1e3))
print('Fr 全程 max %.0f N ; Fl max %.0f N' % (Fr.max(),Fl.max()))
