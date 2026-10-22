import json, numpy as np, sys
sys.path.insert(0, "src")
from pathlib import Path
from velch.profiles import load_profile
cat = json.load(open("diagnostics/crh380a_m_track_catalog.json", encoding="utf-8"))
refs = {(r["index"], r["side"]): r for r in cat["profile_references"]}
right = sorted([r for r in cat["profile_references"] if r["side"]=="right"], key=lambda r: r["index"])
ss = [r["station_m"] for r in right]
gaps = np.diff(sorted(set(ss)))
print("station gaps: n=", len(gaps), "min %.4f median %.3f max %.3f" % (gaps.min(), np.median(gaps), gaps.max()))
print("unique stations:", len(set(ss)), "refs:", len(ss))
# spacing histogram
import collections
c = collections.Counter(np.round(gaps,3).tolist())
print("gap histogram (top):", sorted(c.items())[:5], "...", sorted(c.items())[-5:])
print()
print("=== coincident station pairs: profile step magnitude ===")
for pair in cat["coincident_stations"]:
    i, j = pair["indices"]
    a = refs[(i,"right")]; b = refs[(j,"right")]
    pa = load_profile(Path(a["path"]), file_format="prr", surface="rail_top")
    pb = load_profile(Path(b["path"]), file_format="prr", surface="rail_top")
    lo = max(pa.y_m[0], pb.y_m[0]); hi = min(pa.y_m[-1], pb.y_m[-1])
    y = np.unique(np.concatenate([[lo,hi], pa.y_m[(pa.y_m>lo)&(pa.y_m<hi)], pb.y_m[(pb.y_m>lo)&(pb.y_m<hi)]]))
    dz = pb.z_at(y) - pa.z_at(y)
    k = int(np.argmax(np.abs(dz)))
    print(f"s={pair['station_m']:8.3f} idx {i:3d}/{j:3d}  max|dz|={abs(dz[k])*1000:8.3f} mm at y={y[k]*1000:7.2f} mm   z_a={pa.z_at(y[k])*1000:7.3f} z_b={pb.z_at(y[k])*1000:7.3f}")
    print(f"          profile y-range: a[{pa.y_m[0]*1000:.2f},{pa.y_m[-1]*1000:.2f}] b[{pb.y_m[0]*1000:.2f},{pb.y_m[-1]*1000:.2f}]  npts {len(pa.y_m)}/{len(pb.y_m)}")
