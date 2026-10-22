import json, pathlib, subprocess, sys, csv, numpy as np
src = json.load(open(r"validation/crh380a_m/case_B_turnout.json", encoding="utf-8"))
base = json.loads(json.dumps(src)); base["case_id"]="b_nowin_0p42"; base["run"]["duration_s"]=0.42
win  = json.loads(json.dumps(src)); win["case_id"]="b_win_0p42"; win["run"]["duration_s"]=0.42
win["run"]["contact_search_half_width_m"]=0.002
for tag,c in (("nowin",base),("win",win)):
    p = pathlib.Path(f"validation/crh380a_m/case_chk_{tag}.json"); p.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    r = subprocess.run([sys.executable,"-m","velch","run-vehicle",str(p),"--output",f"validation/crh380a_m/out_chk_{tag}"],capture_output=True,text=True,encoding="utf-8",errors="replace")
    print(tag, r.returncode, (r.stdout or r.stderr or "").strip()[:200])
def load(tag):
    with open(f"validation/crh380a_m/out_chk_{tag}/history.csv",newline="",encoding="utf-8") as f:
        rd=csv.reader(f); h=next(rd); d=np.array([[float(v) for v in row] for row in rd])
    return h,d
h1,d1 = load("nowin"); h2,d2 = load("win")
print("rows", d1.shape, d2.shape)
n = min(d1.shape[0], d2.shape[0])
col = [i for i,c in enumerate(h1) if c.endswith("_normal_n")]
# also compare to the old baseline (numpy stencil)
with open(r"validation/crh380a_m/out_B_1p2s_fast/history.csv",newline="",encoding="utf-8") as f:
    rd=csv.reader(f); ho=next(rd); do=np.array([[float(v) for v in row] for row in rd])
co = [i for i,c in enumerate(ho) if c.endswith("_normal_n")]
print("nowin vs win      : max|dF| %.6f N" % np.abs(d1[:n][:,col]-d2[:n][:,col]).max())
print("nowin vs oldbase  : max|dF| %.6f N" % np.abs(d1[:n][:,col]-do[:n][:,co]).max())
print("win   vs oldbase  : max|dF| %.6f N" % np.abs(d2[:n][:,col]-do[:n][:,co]).max())
d = np.abs(d1[:n][:,col]-d2[:n][:,col]).max(axis=1)
i = int(np.argmax(d > 1e-6))
print("first divergence sample:", i, "t=", d1[i,0], "dF=", d[i])
