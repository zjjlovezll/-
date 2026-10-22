import json
for tag in ["out_bench_0_cached","out_bench_0_refac"]:
    m = json.load(open(f"validation/crh380a_m/{tag}/manifest.json", encoding="utf-8"))
    s = m["summary"]
    print(tag)
    print("   case_sha256", m.get("case_sha256","")[:16])
    for k in ("result_status","nfev","njev","runtime_s"): print("  ",k,s.get(k))
    print("   gates", {k:v for k,v in (s.get("gates") or {}).items() if v not in (True,0,0.0)} or "all pass")
    print("   max_pen", s.get("max_penetration_m"), "turnout_peak", s.get("peak_normal_n"))
