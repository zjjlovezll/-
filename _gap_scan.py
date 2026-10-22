import json, numpy as np, sys, pathlib
sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\src")
from velch.profiles import load_profile
cat = json.load(open(r"F:\ai道岔状态反演辨识\Velch\diagnostics\crh380a_m_track_catalog.json", encoding="utf-8"))
right = [r for r in cat["profile_references"] if r.get("side")=="right"]
w = load_profile(pathlib.Path(r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database\wheel_rail_profiles\LMA.prw"),
                 file_format="prr", surface="wheel_lower", y_sign=1, z_sign=-1, z_offset_m=-0.43)
wy = np.asarray(w.y_m); wz = np.asarray(w.z_m)
print(f"wheel(R) y[{wy.min()*1e3:.2f},{wy.max()*1e3:.2f}] z[{wz.min()*1e3:.2f},{wz.max()*1e3:.2f}] n={wy.size}")
for s in (79.9206, 80.0044, 80.3413):
    r = min(right, key=lambda r: abs(float(r["station_m"]) - s))
    p = load_profile(pathlib.Path(r["path"]), file_format="prr", surface="rail_top", z_sign=-1, y_offset_m=0.753)
    ry = np.asarray(p.y_m) - 0.753; rz = np.asarray(p.z_m)
    lo = max(wy.min(), ry.min()); hi = min(wy.max(), ry.max())
    g = np.linspace(lo, hi, 6000)
    gap = np.interp(g, wy, wz) - np.interp(g, ry, rz)
    loc = [i for i in range(2, g.size-2) if gap[i] < gap[i-1] and gap[i] <= gap[i+1]]
    loc = sorted(loc, key=lambda i: gap[i])[:4]
    print(f"\nst {r['station_m']}: overlap y_prr[{lo*1e3:.1f},{hi*1e3:.1f}] mm")
    for i in loc:
        print(f"   min y_prr={g[i]*1e3:7.2f} (abs {753+g[i]*1e3:7.2f}) gap={gap[i]*1e3:+8.4f} rail_z={rz[np.argmin(np.abs(ry-g[i]))]*1e3:6.2f}")
    j=int(np.argmin(gap))
    print(f"   global y_prr={g[j]*1e3:7.2f} gap={gap[j]*1e3:+.4f} mm")
