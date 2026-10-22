import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,"src")
from velch.profiles import load_profile
base = Path(r"validation\crh380a_m")
case = json.loads((base/"case_B_turnout.json").read_text(encoding="utf-8"))
rt = {t["id"]: t for t in case["rail_templates"]}
def series(tid, band):
    out=[]
    for st in rt[tid]["stations"]:
        s=st["profile"]
        p=load_profile(base/s["file"], file_format=s["format"], surface="rail_top",
                       y_sign=s["y_sign"], z_sign=s["z_sign"], y_offset_m=s.get("y_offset_m",0.0))
        ys, zs = p.y_m*1e3, p.z_m*1e3
        m=(ys>=band[0])&(ys<=band[1])
        yy, zz = ys[m], zs[m]
        j=int(zz.argmax())
        out.append((st["s_m"], float(zz[j]), float(yy[j]), len(yy)))
    return sorted(out)
band=(725.0,815.0)
r = series("right", band)
arr=np.array([[x[0],x[1],x[2]] for x in r])
print("stations", len(r), " points per section in band:", sorted({x[3] for x in r}))
print(f"crown z: min {arr[:,1].min():.4f} max {arr[:,1].max():.4f} ptp {arr[:,1].max()-arr[:,1].min():.4f} mm")
print(f"crown y: min {arr[:,2].min():.2f} max {arr[:,2].max():.2f} ptp {arr[:,2].max()-arr[:,2].min():.2f} mm")
edge = [x for x in r if x[2] < band[0]+1.0 or x[2] > band[1]-1.0]
print("sections whose crown is at a band edge (suspicious):", len(edge))
for s,z,y,n in r:
    if 81.5 <= s <= 84.0: print(f"  s={s:7.3f} crown z {z:+.4f} at y {y:7.2f}")
print("\nSections where crown z < -0.20 mm:")
for s,z,y,n in r:
    if z < -0.20: print(f"  s={s:7.3f} z {z:+.4f} crown_y {y:7.2f}")
np.savetxt(base/"rail_crown_series.csv", arr, delimiter=",", header="s_m,crown_z_mm,crown_y_mm", comments="")
