import h5py, numpy as np
p=r'simpack-mcp-2021x\results\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat'
f=h5py.File(p,'r')
g=f['timeInt/railWheelPair/SS_F__S_WS_F__RWP_R']
print('keys:',list(g.keys()))
for k in g.keys():
    o=g[k]
    print(k, type(o).__name__, getattr(o,'shape',''), getattr(o,'dtype',''))
    if isinstance(o,h5py.Group): print('   sub:',list(o.keys()))
for name in ('Rail',):
    r=g[name]
    for k in r.keys():
        o=r[k]
        print(' Rail/'+k, type(o).__name__, getattr(o,'shape',''), getattr(o,'dtype',''))
        if isinstance(o,h5py.Dataset):
            a=np.array(o)
            print('   head:',a.ravel()[:6])
