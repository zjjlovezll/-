"""从已重建的整算例派生出 0.05 s 窗口算例（辙叉窗口 / 转辙器窗口）。

用法:
    python make_window_case.py case_F_smooth_all.json frog 69.0
    python make_window_case.py case_F_smooth_all.json switch 42.5
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent


def main() -> None:
    src, tag, x_start = sys.argv[1], sys.argv[2], float(sys.argv[3])
    case = json.loads((BASE / src).read_text(encoding="utf-8"))
    case["case_id"] = f"{case['case_id']}_{tag}_0p05s"
    case["run"]["x_start_m"] = x_start
    case["run"]["duration_s"] = 0.05
    out = f"case_{tag}_{src.replace('case_', '').replace('.json', '')}_0p05s.json"
    (BASE / out).write_text(json.dumps(case, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
    print(f"wrote {out}  x_start={x_start} m  前轴 {x_start + 10:.2f} m → "
          f"{x_start + 10 + 350 / 3.6 * 0.05:.2f} m")


if __name__ == "__main__":
    main()
