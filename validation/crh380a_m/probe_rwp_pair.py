import sys
from pathlib import Path

import h5py
import numpy as np

MAT = Path(r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\results"
           r"\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat")
BASE = "timeInt/RS_result/SRS_S_R/SRS_S_WS_F/SRS_RWP_R"

with h5py.File(MAT, "r") as handle:
    s = np.asarray(handle[f"{BASE}/SRS_RWP_R_Pair/ch_008"]["values"], float).ravel()
    n = np.asarray(handle[f"{BASE}/SRS_RWP_R_1/ch_010"]["values"], float).ravel()
    npatch = np.asarray(handle[f"{BASE}/SRS_RWP_R_Pair/ch_022"]["values"], float).ravel()
    q = np.asarray(handle[f"{BASE}/SRS_RWP_R_Pair/ch_001"]["values"], float).ravel()

print("s range        :", s.min(), s.max())
print("N range        :", n.min(), n.max())
print("Q range        :", q.min(), q.max())
print("n_p unique     :", np.unique(npatch))
for label, series in (("N", n), ("Q", q), ("N+Qz", n + q)):
    i = int(np.argmax(series))
    print(f"{label:5s} argmax {series[i]/1e3:8.2f} kN at s={s[i]:.4f} -> s+17.5={s[i]+17.5:.4f}")
idx = np.argsort(s)
print("\nwindow s+17.5 in [78.8, 82.2]:")
mask = (s[idx] + 17.5 >= 78.8) & (s[idx] + 17.5 <= 82.2)
print("  samples", int(mask.sum()), "N max", n[idx][mask].max() / 1e3, "kN")
print("  corresponding s (unshifted):", s[idx][0] + 0.0)
