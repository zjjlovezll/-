import h5py, numpy as np
P = r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\results\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat"
f = h5py.File(P, "r")
RS = "timeInt/RS_result/SRS_S_R/SRS_S_WS_R/SRS_RWP_R"
def ser(grp, ch):
    return np.asarray(f[f"{RS}/{grp}/{ch}/values"]).ravel()
t = np.asarray(f["timeInt/time/values"]).ravel() if "timeInt/time/values" in f else None
s   = ser("SRS_RWP_R_Pair", "ch_008")
dlz = ser("SRS_RWP_R_Pair", "ch_010")
ydev= ser("SRS_RWP_R_Pair", "ch_009")
np_ = ser("SRS_RWP_R_Pair", "ch_022")
print(f"samples={s.size}  s=[{s.min():.3f},{s.max():.3f}] m")
print(f"np distinct: {sorted(set(np_.astype(int).tolist()))}")
xs = np.arange(79.0, 82.01, 0.1)
idx = np.round((xs - 23.5) / ((140.1671295-23.5)/1.2)).astype(int)
hdr = "   x(m)     s(m)  np    ydev(mm)  dz(mm) | patch: yr(mm)  yw(mm)   A(mm2)  delta(deg)   N(kN)  pen(mm)"
print(hdr)
for x, i in zip(xs, idx):
    i = min(max(i,0), s.size-1)
    line = f"{x:7.2f} {s[i]:8.3f} {int(np_[i]):3d} {ydev[i]*1e3:9.4f} {dlz[i]*1e3:8.4f} |"
    parts=[]
    for p in range(1, 6):
        g = f"SRS_RWP_R_{p}"
        try:
            N = ser(g, "ch_010")[i]; A = ser(g, "ch_006")[i]; d = ser(g,"ch_005")[i]
            yw = ser(g, "ch_002")[i]; yr = ser(f"SRS_RWP_R_{p}_Adv", "ch_003")[i]
            pen= ser(f"SRS_RWP_R_{p}_Adv", "ch_025")[i]
        except KeyError:
            break
        if N > 1.0:
            parts.append(f"#{p} {yr*1e3:7.2f} {yw*1e3:7.2f} {A*1e6:8.2f} {np.degrees(d):8.3f} {N/1e3:8.2f} {pen*1e3:8.4f}")
    print(line + (" " if parts else " no-contact") + "   ||   ".join(parts))
i135 = int(np.argmax(ser("SRS_RWP_R_1","ch_010")))
print(f"\nmax N patch1 = {ser('SRS_RWP_R_1','ch_010')[i135]/1e3:.2f} kN at x={s[i135]:.3f} m  pen={ser('SRS_RWP_R_1_Adv','ch_025')[i135]*1e3:.4f} mm  yr={ser('SRS_RWP_R_1_Adv','ch_003')[i135]*1e3:.2f} mm")
