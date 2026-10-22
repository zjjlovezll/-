import json
from pathlib import Path
base = Path(r"validation\crh380a_m")
for n in ("out_A_1p2s","out_B_1p2s","out_B_1p2s_inverted"):
    m = json.loads((base/n/"manifest.json").read_text(encoding="utf-8"))
    s = m["summary"]
    print(f"=== {n} ===")
    print(" case_sha256", m.get("case_sha256","?")[:16], "| status", s["result_status"], "| gates all:", all(s["gates"].values()))
    print(" dof", s["total_dof"], "patches", s["rail_patch_count"], "nfev", s["solver"]["nfev"],
          "max_pen_mm", round(s["max_penetration_m"]*1e3,4), "fric_excess", s["max_friction_excess_n"])
    print(" preload_res", s["vertical_preload_max_residual_n"], "action_reaction", s["max_translation_balance_error_n"])
    print(" peaks_L", [round(v,1) for k,v in s["peak_normal_force_n"].items() if k.endswith("_left")])
    print(" peaks_R", [round(v,1) for k,v in s["peak_normal_force_n"].items() if k.endswith("_right")])
    print(" energy", round(s["initial_mechanical_energy_j"],1), "->", round(s["final_mechanical_energy_j"],1), "dE", round(s["energy_change_j"],1))
sp = Path(r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\validation\CRH380A_M_2026-10-19\result_summary.json")
if sp.exists():
    d = json.loads(sp.read_text(encoding="utf-8"))
    print("\n=== simpack result_summary keys ===", list(d)[:12])
    print(json.dumps(d, indent=1, ensure_ascii=False)[:1500])
