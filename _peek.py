import json, copy, pathlib
base = pathlib.Path(r"F:\ai道岔状态反演辨识\Velch\validation\crh380a_m\case_C_frog.json")
d = json.loads(base.read_text(encoding="utf-8"))
print("contact:", json.dumps(d["contact"], ensure_ascii=False, indent=1))
print("run:", json.dumps(d["run"], ensure_ascii=False, indent=1))
print("case_id:", d["case_id"])
