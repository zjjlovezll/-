import sys, numpy as np
from pathlib import Path
sys.path.insert(0,"src")
root = Path(r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database")
hits = list(root.rglob("Profile_Mileage_XG_JJ.prr"))
print(hits)
p = hits[0]
txt = p.read_text(encoding="utf-8", errors="replace").splitlines()
print("total lines", len(txt))
for line in txt[:14]: print("  H|", line)
# find point.begin / point.end
idx_b = [i for i,l in enumerate(txt) if l.strip().lower().startswith("point.begin")]
idx_e = [i for i,l in enumerate(txt) if l.strip().lower().startswith("point.end")]
print("begin", idx_b[:6], "end", idx_e[:6])
rows=[]
for i in range(idx_b[0]+1, idx_e[0]):
    t=txt[i].split()
    try: rows.append((float(t[0]), float(t[1])))
    except Exception: pass
a=np.array(rows)
print("n points", a.shape, "y range", a[:,0].min()*1e3, a[:,0].max()*1e3, "z range", a[:,1].min()*1e3, a[:,1].max()*1e3)
# look for gaps in the polyline
dy = np.abs(np.diff(a[:,0]))
big = np.where(dy > 0.005)[0]
print("jumps >5 mm in y:", [(int(i), round(a[i,0]*1e3,2), round(a[i+1,0]*1e3,2)) for i in big[:12]])
print("first 6", (a[:6]*1e3).round(3).tolist())
print("last 6", (a[-6:]*1e3).round(3).tolist())
