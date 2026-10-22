# -*- coding: utf-8 -*-
"""Build a 1 % stiffness variant of the frog case (B3 cross-run reuse check)."""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
BASE = HERE / "case_frog_N_strip05.json"
data = json.loads(BASE.read_text(encoding="utf-8"))
data["case_id"] = "b3_C101"
data["contact"]["effective_radius_m"] = float(data["contact"]["effective_radius_m"]) * 1.01
path = HERE / "case_b3_C101.json"
path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(path)
