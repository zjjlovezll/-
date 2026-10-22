import csv, json
from pathlib import Path
import numpy as np
base = Path(r"validation\crh380a_m")
sp = json.loads(Path(r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\validation\CRH380A_M_2026-10-19\result_summary.json").read_text(encoding="utf-8"))
cr = sp["front_wheelset_x_crossings_of_duplicate_stations"]
print(json.dumps(cr, indent=1, ensure_ascii=False)[:900])
