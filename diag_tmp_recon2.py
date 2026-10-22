import re
from pathlib import Path
import numpy as np
prof = Path(r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database\wheel_rail_profiles")
def points(p):
    t = p.read_bytes().decode("utf-8","replace")
    s = t.find("point.begin"); e = t.find("point.end", s+11)
    rows=[]
    for line in t[s+11:e].splitlines():
        line=line.strip()
        if not line or line.startswith("!"): continue
        f=line.split()
        if len(f)>=2:
            try: rows.append((float(f[0]),float(f[1])))
            except ValueError: pass
    return np.array(rows)
for name in ["LMA.prw","LM.prw","Wheel_LMA.prw","Profile_Mileage_JBG.prr","Profile_Mileage_R50.prr",
             "Profile_Mileage_R50.048.prr","Profile_Mileage_R0.prr"]:
    p=prof/name
    if not p.is_file():
        print(name,"MISSING"); continue
    a=points(p)
    print(f"{name:32s} n={len(a):5d} y=[{a[:,0].min():+.5f},{a[:,0].max():+.5f}] z=[{a[:,1].min():+.5f},{a[:,1].max():+.5f}]")
