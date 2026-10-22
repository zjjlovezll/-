import h5py, numpy as np
P = r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\results\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat"
f = h5py.File(P, "r")
RS = "timeInt/RS_result/SRS_S_R/SRS_S_WS_R/SRS_RWP_R"
def ser(g,c): return np.asarray(f[f"{RS}/{g}/{c}/values"]).ravel()
s = ser("SRS_RWP_R_Pair","ch_008")
N = ser("SRS_RWP_R_1","ch_010"); pen = ser("SRS_RWP_R_1_Adv","ch_025"); A = ser("SRS_RWP_R_1","ch_006")
ok = (N > 1000) & (pen > 1e-9)
C = N[ok] / pen[ok]**1.5
print(f"patch1: {ok.sum()}/{N.size} samples with N>1kN")
print(f"pen  : {pen[ok].min()*1e3:.4f} .. {pen[ok].max()*1e3:.4f} mm  (median {np.median(pen[ok])*1e3:.4f})")
print(f"N    : {N[ok].min()/1e3:.2f} .. {N[ok].max()/1e3:.2f} kN")
print(f"implied C=N/pen^1.5 : median {np.median(C):.3e}  p10 {np.percentile(C,10):.3e}  p90 {np.percentile(C,90):.3e}  ratio(p90/p10) {np.percentile(C,90)/np.percentile(C,10):.2f}")
print(f"A    : {A[ok].min()*1e6:.1f} .. {A[ok].max()*1e6:.1f} mm2")
# correlation of C with patch area -> evidence of distributed contact
r = np.corrcoef(np.log(C), np.log(A[ok]))[0,1]
print(f"corr(ln C, ln A) = {r:.3f}")
# split: normal running vs frog knife-edge
frog = ok & (s>=79.15) & (s<=80.10)
norm = ok & ((s<79.15) | (s>82.5))
for nm, m in (("正常段", norm), ("辙叉尖轨段 79.15-80.10", frog)):
    if m.sum()>3:
        print(f"{nm:26s} n={m.sum():4d}  pen_med={np.median(pen[m])*1e3:7.4f} mm  N_med={np.median(N[m])/1e3:7.2f} kN  A_med={np.median(A[m])*1e6:6.2f} mm2  C_med={np.median(C[m]):.3e}")
