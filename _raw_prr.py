import json, numpy as np, pathlib
cat = json.load(open(r"F:\ai道岔状态反演辨识\Velch\diagnostics\crh380a_m_track_catalog.json", encoding="utf-8"))
right = [r for r in cat["profile_references"] if r.get("side")=="right"]
def pts_of(p):
    out=[]
    for line in pathlib.Path(p).read_text(encoding="utf-8", errors="ignore").splitlines():
        parts=line.split()
        if len(parts)>=2:
            try: out.append((float(parts[0]), float(parts[1])))
            except ValueError: pass
    return np.array(out)*1e3
for s in (79.917, 80.014, 80.352, 80.500, 80.700, 81.000):
    r = min(right, key=lambda r: abs(float(r["station_m"]) - s))
    a = pts_of(r["path"])
    sel = a[(a[:,0]>=725)&(a[:,0]<=770)]; sel = sel[np.argsort(sel[:,0])]
    print(f"\nst {r['station_m']:8.4f} {pathlib.Path(r['path']).name}: {len(a)} pts y[{a[:,0].min():.1f},{a[:,0].max():.1f}] z[{a[:,1].min():.1f},{a[:,1].max():.1f}]")
    print("   ", "  ".join(f"{y:.1f}/{z:.2f}" for y,z in sel[:34]))
