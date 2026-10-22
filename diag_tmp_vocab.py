import re, collections, os
base = r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database\mbs_db_substructure"
files = ["CRH380A_M_Carbody.spck", "CRH380A_M_Bogie.spck", "CRH380A_M_Wheelset.spck"]
pat = re.compile(r"^\s*([A-Za-z_][\w\.]*)\s*\(\s*(\$[\w]+)\s*\)\s*=\s*(.*?)\s*(?:!\s*(.*))?$")
for fn in files:
    p = os.path.join(base, fn)
    txt = open(p, "r", encoding="utf-8", errors="replace").read()
    print("="*90); print(fn, "lines", txt.count("\n"))
    keys = collections.Counter()
    samples = {}
    nstmt = 0
    for line in txt.splitlines():
        m = pat.match(line)
        if not m: continue
        nstmt += 1
        k = m.group(1)
        keys[k] += 1
        if k not in samples:
            samples[k] = (m.group(2), m.group(3)[:70], (m.group(4) or "")[:40])
    print("statements", nstmt, "unique keys", len(keys))
    for k, c in keys.most_common():
        obj, val, com = samples[k]
        print(f"  {k:34s} {c:5d}  e.g. {obj} = {val}  !{com}")
