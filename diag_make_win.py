import json, pathlib
src = json.load(open(r"validation/crh380a_m/case_bench_0.json", encoding="utf-8"))
print("base run block:", {k: src["run"][k] for k in ("x_start_m","duration_s","method","output_step_s","max_solver_step_s","rtol","atol")})
made = []
for tag, half in (("w2", 0.0002), ("w5", 0.0005), ("w20", 0.002)):
    for xs in (13.5, 60.0, 78.0, 80.0):
        c = json.loads(json.dumps(src))
        c["case_id"] = f"crh380a_m_bench_x{xs:g}_{tag}"
        c["run"]["x_start_m"] = xs
        c["run"]["contact_search_half_width_m"] = half
        p = pathlib.Path(f"validation/crh380a_m/case_win_{tag}_x{xs:g}.json")
        p.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
        made.append(p.name)
print(len(made), "cases:", made[:6], "...")
