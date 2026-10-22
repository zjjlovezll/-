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
    return np.array(out)
for s in (79.9206, 80.0044, 80.3413, 80.5312, 80.7211):
    r = min(right, key=lambda r: abs(float(r["station_m"]) - s))
    a = pts_of(r["path"]) * 1e3   # mm
    sel = a[(a[:,0]>=-30)&(a[:,0]<=30)]; sel = sel[np.argsort(sel[:,0])]
    print(f"\nst {r['station_m']:8.4f} {pathlib.Path(r['path']).name}  ({len(a)} pts)")
    if not len(sel):
        print("   no points with y in [-30,30] mm"); continue
    segs=[]; cur=[sel[0]]
    for p in sel[1:]:
        if abs(p[0]-cur[-1][0])>0.6 or abs(p[1]-cur[-1][1])>0.6: segs.append(cur); cur=[p]
        else: cur.append(p)
    segs.append(cur)
    for k,seg in enumerate(segs):
        ys=[q[0] for q in seg]; zs=[q[1] for q in seg]
        i=int(np.argmax(zs))
        print(f"   seg{k}: y {min(ys):7.2f}..{max(ys):7.2f}  z {min(zs):7.3f}..{max(zs):7.3f}  crown@y={seg[i][0]:f} n={len(seg)}")
