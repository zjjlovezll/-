import sys, json, numpy as np
sys.path.insert(0,"src")
from velch.profiles import load_profile
cat = json.load(open(r"diagnostics/crh380a_m_track_catalog.json", encoding="utf-8"))
refs = [r for r in cat["profile_references"] if r.get("side") == "right"]
rows = []
for i, r in enumerate(refs):
    try:
        prof = load_profile(r["path"], file_format="prr", surface="rail_top", y_sign=1, z_sign=-1, y_offset_m=0.753)
    except Exception as e:
        rows.append((i, r["station_m"], -1, -1, "ERR " + str(e)[:40])); continue
    y, z = prof.y_m, prof.z_m
    top = float(z.max()); mask = z > top - 0.005
    d = np.diff(np.concatenate(([0], mask.astype(int), [0])))
    starts = np.flatnonzero(d == 1); ends = np.flatnonzero(d == -1)
    bands = [(float(y[a]), float(y[b-1])) for a, b in zip(starts, ends)]
    wide = [b for b in bands if b[1]-b[0] > 0.004]
    rows.append((i, float(r["station_m"]), len(bands), len(wide),
                 "; ".join("%.1f..%.1f" % (a*1e3, b*1e3) for a, b in wide)))
multi = [x for x in rows if x[2] > 1]
print("stations with >1 band:", len(multi), "of", len(rows))
for x in multi[:16]:
    print("  idx %3d s=%-8.3f bands=%d wide=%d  %s" % (x[0], x[1], x[2], x[3], x[4]))
w = [x[3] for x in rows if x[2] >= 0]
print("wide-band count distribution:", {k: w.count(k) for k in sorted(set(w))})
