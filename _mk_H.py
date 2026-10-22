import json, pathlib, math
base = pathlib.Path(r"F:\ai道岔状态反演辨识\Velch\validation\crh380a_m\case_C_frog.json")
d = json.loads(base.read_text(encoding="utf-8"))
E = 113932291666.667
C_target = 1.117e11
R = (C_target / ((4.0/3.0)*E))**2
print(f"target C={C_target:.4e} -> effective_radius_m={R:.6f}")
d["case_id"] = "crh380a_m_case_H_stiff"
d["purpose_detail"] = "frog window with contact stiffness matched to Simpack empirical law (C=1.117e11)"
d["contact"]["effective_radius_m"] = round(R, 6)
p = base.with_name("case_H_stiff.json")
p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote", p)
print("C_check:", (4.0/3.0)*E*math.sqrt(R))
