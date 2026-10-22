import h5py, numpy as np
P = r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\results\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat"
f = h5py.File(P, "r")
RS = "timeInt/RS_result/SRS_S_R/SRS_S_WS_R/SRS_RWP_R"
def ser(g, c): return np.asarray(f[f"{RS}/{g}/{c}/values"]).ravel()
s = ser("SRS_RWP_R_Pair", "ch_008"); npv = ser("SRS_RWP_R_Pair","ch_022")
dlz = ser("SRS_RWP_R_Pair","ch_010"); ydev = ser("SRS_RWP_R_Pair","ch_009")
mask = (s >= 78.8) & (s <= 82.2)
ii = np.where(mask)[0]
print(f"window samples {ii.size}, ds={np.diff(s[ii]).mean()*1e3:.2f} mm")
cols = {}
for p in range(1,6):
    try:
        cols[p] = dict(N=ser(f"SRS_RWP_R_{p}","ch_010"), yr=ser(f"SRS_RWP_R_{p}_Adv","ch_003"),
                       pen=ser(f"SRS_RWP_R_{p}_Adv","ch_025"), A=ser(f"SRS_RWP_R_{p}","ch_006"))
    except KeyError: pass
print("   s(m)   np  dz(mm)    |  patch#  N(kN)  pen(mm)   yr(mm)   A(mm2)")
step = max(1, ii.size // 40)
for i in ii[::step]:
    row = f"{s[i]:7.3f} {int(npv[i]):3d} {dlz[i]*1e3:7.4f}   |"
    parts=[]
    for p,d in cols.items():
        if d["N"][i] > 1.0:
            parts.append(f"#{p} {d['N'][i]/1e3:7.2f} {d['pen'][i]*1e3:8.4f} {d['yr'][i]*1e3:8.2f} {d['A'][i]*1e6:8.2f}")
    print(row + ("   " + " || ".join(parts) if parts else "  no contact"))
allN = np.maximum.reduce([d["N"] for d in cols.values()])
print(f"\nN range in window: {allN[ii].min()/1e3:.2f} .. {allN[ii].max()/1e3:.2f} kN ; pen range {min(d['pen'][ii].min() for d in cols.values())*1e3:.4f} .. {max(d['pen'][ii].max() for d in cols.values())*1e3:.4f} mm")
print(f"no-contact samples in window: {int((allN[ii] <= 1.0).sum())}")
k = ii[np.argmax(allN[ii])]
print(f"peak at s={s[k]:.3f} m, N={allN[k]/1e3:.2f} kN, patches={int(npv[k])}")
