import json, csv, numpy as np
def load(tag):
    with open(f"validation/crh380a_m/{tag}/history.csv", newline="", encoding="utf-8") as f:
        rd = csv.reader(f); h = next(rd); d = np.array([[float(v) for v in row] for row in rd])
    return h, d
for tag in ("out_B_1p2s_fast", "out_B_1p2s_w2"):
    m = json.load(open(f"validation/crh380a_m/{tag}/manifest.json", encoding="utf-8"))
    s = m["summary"]; h, d = load(tag)
    ix = {n: i for i, n in enumerate(h)}
    print(tag)
    print("  status", s.get("result_status"), "| max_pen %.4f mm" % (s.get("max_penetration_m", 0)*1e3),
          "| runtime_s", s.get("runtime_s"), "| nfev", s.get("nfev"))
    for side in ("left", "right"):
        c = ix[f"axle1_{side}_normal_n"]; a = ix[f"axle1_{side}_active"]
        f = d[:, c]
        print("  %-5s normal N: min %9.1f  mean %9.1f  max %9.1f | active %d/%d | zero samples %d"
              % (side, f.min(), f.mean(), f.max(), int(d[:, a].sum()), d.shape[0], int((f == 0).sum())))
    print("  energy_change_j", round(s.get("energy_change_j", 0), 1))
    print("  gates non-zero:", {k: v for k, v in (s.get("gates") or {}).items() if v not in (True, 0, 0.0)} or "all pass")
