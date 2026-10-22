import json, pathlib
src = json.load(open(r"validation/crh380a_m/case_B_turnout.json", encoding="utf-8"))
src["case_id"] = "crh380a_m_turnout_win2mm"
src["run"]["contact_search_half_width_m"] = 0.002
pathlib.Path("validation/crh380a_m/case_B_turnout_w2.json").write_text(
    json.dumps(src, ensure_ascii=False, indent=2), encoding="utf-8")
print("run block:", json.dumps(src["run"], ensure_ascii=False)[:400])
