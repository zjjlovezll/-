"""Clone a case with the strip-integral normal law and run the A/B.

Usage:
    python -X utf8 validation\\crh380a_m\\ab_normal_policy.py [base_case] [tag]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / "case_frog_S_local_rise0.4_0p05s.json"


def clone(policy: str, name: str, dy: float | None = None) -> Path:
    data = json.loads(BASE.read_text(encoding="utf-8"))
    data["case_id"] = name
    contact = data["contact"]
    contact["normal_policy"] = policy
    contact["stiffness_policy"] = "local_circular"
    if dy is not None:
        contact["strip_dy_m"] = dy
    path = HERE / f"{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def run(case: Path, out: Path) -> None:
    subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle",
                    str(case), "--output", str(out)], cwd=ROOT, check=False)


def main() -> int:
    tag = sys.argv[2] if len(sys.argv) > 2 else ""
    variants = {
        "out_N_point": ("point_hertz", "case_frog_N_point"),
        "out_N_strip": ("strip_integral", "case_frog_N_strip"),
        "out_N_strip05": ("strip_integral", "case_frog_N_strip05"),
    }
    for out_name, (policy, case_name) in variants.items():
        dy = 5.0e-4 if out_name.endswith("05") else None
        case = clone(policy, case_name + tag, dy)
        run(case, HERE / (out_name + tag))
        manifest = HERE / (out_name + tag) / "manifest.json"
        if not manifest.is_file():
            print(f"{out_name}: FAILED (no manifest)")
            continue
        summary = json.loads(manifest.read_text(encoding="utf-8"))["summary"]
        print(f"{out_name:16s} {summary['result_status']:20s} "
              f"peakR {summary['peak_normal_force_n']['axle1_right'] / 1e3:7.2f} kN "
              f"activeR {summary['active_output_samples']['axle1_right']:4d} "
              f"maxpen {summary['max_penetration_m'] * 1e3:6.4f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
