"""Full-length (1.2 s) A/B of the strip-integral normal law on the oracle case."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / "case_A_final_law.json"


def main() -> int:
    data = json.loads(BASE.read_text(encoding="utf-8"))
    data["case_id"] = "crh380a_m_final_strip"
    data["contact"]["normal_policy"] = "strip_integral"
    data["contact"]["stiffness_policy"] = "local_circular"
    case = HERE / "case_A_final_strip.json"
    case.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = HERE / "out_final_strip1p2s"
    subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle",
                    str(case), "--output", str(out)], cwd=ROOT, check=False)
    manifest = out / "manifest.json"
    if not manifest.is_file():
        print("strip 1.2 s: FAILED")
        return 1
    summary = json.loads(manifest.read_text(encoding="utf-8"))["summary"]
    print(f"strip 1.2 s: {summary['result_status']} "
          f"peakR {summary['peak_normal_force_n']['axle1_right'] / 1e3:.2f} kN "
          f"peakL {summary['peak_normal_force_n']['axle1_left'] / 1e3:.2f} kN "
          f"activeR {summary['active_output_samples']['axle1_right']} "
          f"maxpen {summary['max_penetration_m'] * 1e3:.4f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
