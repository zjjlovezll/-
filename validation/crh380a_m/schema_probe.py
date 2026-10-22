import json
import pathlib

p = pathlib.Path("case_C_bodies.json")
case = json.loads(p.read_text(encoding="utf-8"))
for t in case["rail_templates"]:
    print("template", t["id"], "keys", list(t))
rt = [t for t in case["rail_templates"] if "bodies" in t]
rt = rt[0]
print("chosen", rt["id"])
for b in rt["bodies"]:
    print("body", b["id"], "keys", list(b), "n_st", len(b["stations"]))
    print("  station[0] =", json.dumps(b["stations"][0], ensure_ascii=False))
    print("  station[-1]=", json.dumps(b["stations"][-1], ensure_ascii=False))
    ss = [s["s_m"] for s in b["stations"]]
    print("  s range", ss[0], ss[-1])
