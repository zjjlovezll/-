import json, collections
from pathlib import Path
cat = json.load(open("diagnostics/crh380a_m_track_catalog.json", encoding="utf-8"))
refs = cat["profile_references"]
print("total refs", len(refs), "summary", cat["summary"])
by = collections.Counter((r["source_model"].split("\\")[-1], r["side"]) for r in refs)
for k,v in by.items(): print(k, v)
print("\n--- LEFT rail refs ---")
for r in refs:
    if r["side"] == "left":
        print(r["index"], r["station_m"], r["station_expression"], r["filename"], (r["path"] or "")[-60:])
print("\n--- right: station min/max/count ---")
right = [r for r in refs if r["side"]=="right"]
ss = sorted(r["station_m"] for r in right)
print(len(ss), ss[0], ss[-1])
print("first 8 stations:", ss[:8])
print("\n--- coincident ---")
for c in cat["coincident_stations"]:
    print(c["side"], c["station_m"], c["indices"], "distinct" if c["distinct_contents"] else "same")
