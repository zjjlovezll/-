import os, re, glob
base = r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database"
print("base exists:", os.path.exists(base))
sub = os.path.join(base, "mbs_db_substructure")
print("sub exists:", os.path.exists(sub))
if os.path.exists(sub):
    for f in sorted(os.listdir(sub)):
        p = os.path.join(sub, f)
        if os.path.isfile(p):
            print(f"  {f:45s} {os.path.getsize(p):>12,}")
        else:
            print(f"  {f:45s} <dir>")
