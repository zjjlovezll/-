import json, pathlib, subprocess, sys, time, csv, numpy as np
src = json.load(open(r"validation/crh380a_m/case_B_turnout.json", encoding="utf-8"))
def make(tag, dur, half):
    c = json.loads(json.dumps(src)); c["case_id"]=tag; c["run"]["duration_s"]=dur
    if half is not None: c["run"]["contact_search_half_width_m"]=half
    p = pathlib.Path(f"validation/crh380a_m/case_chk_{tag}.json")
    p.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    t0=time.perf_counter()
    r = subprocess.run([sys.executable,"-m","velch","run-vehicle",str(p),"--output",f"validation/crh380a_m/out_chk_{tag}"],
                       capture_output=True,text=True,encoding="utf-8",errors="replace")
    print("%-12s rc=%d wall=%6.2fs %s" % (tag, r.returncode, time.perf_counter()-t0, "" if r.returncode==0 else r.stderr.strip()[:160]))
make("w2fix_0p42", 0.42, 0.002)
def load(tag):
    with open(f"validation/crh380a_m/out_chk_{tag}/history.csv",newline="",encoding="utf-8") as f:
        rd=csv.reader(f); h=next(rd); d=np.array([[float(v) for v in row] for row in rd])
    return h,d
h1,d1 = load("nowin"); h2,d2 = load("w2fix_0p42")
n = min(len(d1),len(d2)); col=[i for i,c in enumerate(h1) if c.endswith("_normal_n")]
print("rows", len(d1), len(d2), " vs global: max|dF| %.4f N  mean %.4f N" % (np.abs(d1[:n][:,col]-d2[:n][:,col]).max(), np.abs(d1[:n][:,col]-d2[:n][:,col]).mean()))
