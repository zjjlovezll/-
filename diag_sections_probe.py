import json, numpy as np, sys, collections
sys.path.insert(0,'src')
from velch.profiles import load_profile
case=json.load(open('validation/crh380a_m/case_B_turnout.json',encoding='utf-8'))
right=[t for t in case['rail_templates'] if t['id']=='right'][0]
out=[]
for s in right['stations']:
    spec=s['profile']
    prof=load_profile(spec['file'],file_format='prr',surface='rail_top',
                      y_sign=spec['y_sign'],z_sign=spec['z_sign'],y_offset_m=spec['y_offset_m'])
    y=prof.y_m; z=prof.z_m
    top=z.max(); ty=y[int(z.argmax())]
    # 轨顶带：距最高点 5mm 以内的连续 y 段
    band=z>top-0.005
    nseg=int(np.sum(np.diff(np.concatenate([[0],band.astype(int),[0]]))==1))
    spans=[]
    i=0
    while i<len(band):
        if band[i]:
            j=i
            while j+1<len(band) and band[j+1]: j+=1
            spans.append((y[i]*1000,y[j]*1000)); i=j+1
        else: i+=1
    out.append(dict(s=s['s_m'],id=s['id'],y_in=y[0]*1000,y_out=y[-1]*1000,top_y=ty*1000,top_z=top*1000,
                    nseg=nseg,spans=spans,npts=len(y)))
print('n',len(out))
a=np.array([[r['y_in'],r['y_out'],r['top_y'],r['top_z'],r['nseg']] for r in out])
for i,n in enumerate(['y_in','y_out','top_y','top_z','nseg']):
    lo=float(a[:,i].min()); hi=float(a[:,i].max())
    print('%-7s min %10.3f max %10.3f' % (n,lo,hi))
print('\n轨顶带段数 nseg 分布:',collections.Counter(a[:,4].astype(int)).most_common())
print('top_z 分布(0.01mm):',collections.Counter(np.round(a[:,3],2)).most_common(8))
print('')
print('-- 多段站位（nseg>=2）示例：')
k=0
for r in out:
    if r['nseg']>=2 and k<12:
        print('  s=%8.3f %s y_in=%8.3f y_out=%8.3f top=(%.3f,%.3f) spans=%s' % (r['s'],r['id'],r['y_in'],r['y_out'],r['top_y'],r['top_z'],['%.1f..%.1f'%sp for sp in r['spans']]))
        k+=1
print('')
print('-- top_y 与 y_in 的差（mm）分布：')
d=a[:,2]-a[:,0]
print('  min %.3f max %.3f' % (float(d.min()),float(d.max())))
print('  top_y 落在 745..760 的站位数:',int(np.sum((a[:,2]>745)&(a[:,2]<760))),'/',len(a))
