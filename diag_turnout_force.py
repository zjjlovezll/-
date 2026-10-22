import csv, numpy as np
p='validation/crh380a_m/out_B_1p2s_fast/history.csv'
rows=list(csv.DictReader(open(p,encoding='utf-8')))
def col(n): return np.array([float(r[n]) for r in rows])
t=col('time_s'); x=col('axle1_x_m')
for side in ('right','left'):
    F=col(f'axle1_{side}_normal_n'); pen=col(f'axle1_{side}_penetration_m'); act=col(f'axle1_{side}_active')
    print(f'--- {side}: F max {F.max():.1f} at t={t[F.argmax()]:.4f} x={x[F.argmax()]:.3f} pen={pen[F.argmax()]*1000:.4f}mm act={act[F.argmax()]:.0f}')
    print(f'    active samples {int(act.sum())}/{len(act)}; pen max {pen.max()*1000:.4f} mm; pen>0.5mm samples {int((pen>0.0005).sum())}')
    # 分段：打印 x 在 78..84 m 区间的采样
    m=(x>79.5)&(x<82.5)
    print('    x window 79.5-82.5 m: F range', F[m].min(), F[m].max(), 'act0 count', int((act[m]==0).sum()))
y=col('axle1_y_m'); z=col('axle1_z_m'); roll=col('axle1_roll_rad'); yaw=col('axle1_yaw_rad')
print(f'axle1 y range {y.min()*1000:.2f}..{y.max()*1000:.2f} mm  z range {z.min()*1000:.2f}..{z.max()*1000:.2f} mm  roll {roll.min():.4f}..{roll.max():.4f}  yaw {yaw.min():.4f}..{yaw.max():.4f}')
ip=int(col('axle1_right_normal_n').argmax())
print(f'at peak: y={y[ip]*1000:.3f} mm z={z[ip]*1000:.3f} mm roll={roll[ip]:.5f} yaw={yaw[ip]:.5f} vy={col("axle1_y_m_per_s")[ip]:.4f} vz={col("axle1_z_m_per_s")[ip]:.4f}')
# 接触丢失区间
act=col('axle1_right_active'); lost=np.where(act==0)[0]
if len(lost):
    print(f'contact lost samples {len(lost)}; x from {x[lost].min():.3f} to {x[lost].max():.3f}; t {t[lost].min():.4f}..{t[lost].max():.4f}')
    # 每个连续段
    br=np.split(lost, np.where(np.diff(lost)>1)[0]+1)
    for b in br[:12]:
        print(f'   seg n={len(b)} x {x[b[0]]:.3f}->{x[b[-1]]:.3f} F_after={col("axle1_right_normal_n")[b[-1]+1]:.0f} pen_after={col("axle1_right_penetration_m")[b[-1]+1]*1000:.3f}mm')
