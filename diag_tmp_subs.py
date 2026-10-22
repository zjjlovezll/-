import re, os, json
base = r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database\mbs_db_substructure"
files = {"carbody":"CRH380A_M_Carbody.spck","bogie":"CRH380A_M_Bogie.spck","wheelset":"CRH380A_M_Wheelset.spck"}
pat = re.compile(r"^\s*([A-Za-z_][\w\.]*)\s*\(\s*(\$[\w]+)\s*\)\s*=\s*(.*?)\s*(?:!\s*(.*))?$")
num = re.compile(r"^-?[\d.]+(?:[eE][-+]?\d+)?$")
for tag, fn in files.items():
    txt = open(os.path.join(base, fn), "r", encoding="utf-8", errors="replace").read()
    subs = {}
    for line in txt.splitlines():
        m = pat.match(line)
        if not m: continue
        k, obj, val = m.group(1), m.group(2), m.group(3).strip()
        if k == "subvar.str":
            subs[obj] = val.strip("'")
    print("="*80); print(f"{tag}: {len(subs)} subvars")
    for k, v in subs.items():
        if num.match(v):
            print(f"  {k:34s} = {v}")
