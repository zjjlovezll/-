import re, json, collections
from pathlib import Path
db = Path(r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database")
prof = db/"wheel_rail_profiles"
print("profiles dir count:", len(list(prof.glob("*"))))
print("prw files:", [p.name for p in prof.glob("*.prw")])
def head(p, n=6):
    t = p.read_bytes().decode("utf-8","replace")
    m = re.search(r"^\s*type\s*=\s*([01])\b", t, re.M)
    u = re.search(r"^\s*units\.len\s*=\s*['\"]?([^'\"\s]+)", t, re.M)
    return m.group(1) if m else None, u.group(1) if u else None, t.splitlines()[:n]
for name in ["Profile_Mileage_R50.048.prr","Profile_Mileage_JBG.prr","Profile_Mileage_R50.prr"]:
    p = prof/name
    if p.is_file():
        print(name, head(p)[:2])
for p in list(prof.glob("*.prw")):
    print("PRW", p.name, head(p)[:2])
