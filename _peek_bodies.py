import json
d = json.load(open(r"F:\ai道岔状态反演辨识\Velch\validation\crh380a_m\case_C_frog.json", encoding="utf-8"))
for t in d["rail_templates"]:
    if not t.get("bodies"): 
        st = t["stations"]; ss = sorted(float(x["s_m"]) for x in st)
        print(f"template {t['id']}: single, n={len(st)}, s=[{ss[0]:.3f},{ss[-1]:.3f}]")
        continue
    for b in t["bodies"]:
        st = b["stations"]; ss = sorted(float(x["s_m"]) for x in st)
        print(f"template {t['id']} body {b['id']:8s} n={len(st):4d} s=[{ss[0]:.4f},{ss[-1]:.4f}] lo={b.get('s_lo_m')} hi={b.get('s_hi_m')}")
        print("   first:", json.dumps(st[0], ensure_ascii=False)[:160])
