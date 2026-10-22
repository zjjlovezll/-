"""A/B: grid vs patch geometry policy on the frog window (roadmap S1-c).

Clones a case, switches ``contact.geometry_policy``, runs both through the CLI
and prints the comparison. Kept as a script so the exact JSON that produced the
report is reproducible.

Run:  python -X utf8 validation\\crh380a_m\\ab_geometry_policy.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "validation" / "crh380a_m" / "case_frog_S_local_rise0.4_0p05s.json"
OUT = ROOT / "validation" / "crh380a_m"


def clone(policy: str, name: str) -> Path:
    data = json.loads(BASE.read_text(encoding="utf-8"))
    data["case_id"] = name
    data["contact"]["geometry_policy"] = policy
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def run(case: Path, out_dir: Path) -> dict:
    subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle",
                    str(case), "--output", str(out_dir)],
                   cwd=ROOT, check=False)
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = manifest["summary"]
    return {
        "status": summary["result_status"],
        "peak_right_n": summary["peak_normal_force_n"].get("axle1_right", 0.0),
        "peak_left_n": summary["peak_normal_force_n"].get("axle1_left", 0.0),
        "max_pen_mm": summary["max_penetration_m"] * 1e3,
        "active_right": summary.get("active_output_samples", {}).get("axle1_right"),
        "runtime_s": round(float(summary.get("runtime_s", 0.0)), 2),
    }


def main() -> int:
    rows = {}
    for policy, name in (("grid", "case_frog_T_grid_0p05s"),
                         ("patch", "case_frog_T_patch_0p05s")):
        case = clone(policy, name)
        rows[policy] = run(case, OUT / f"out_T_{policy}")
        print(policy, rows[policy])
    grid, patch = rows["grid"], rows["patch"]
    print(f"\npeak right: {grid['peak_right_n'] / 1e3:.2f} -> "
          f"{patch['peak_right_n'] / 1e3:.2f} kN "
          f"({(patch['peak_right_n'] / grid['peak_right_n'] - 1) * 100:+.1f}%)")
    print(f"max penetration: {grid['max_pen_mm']:.4f} -> {patch['max_pen_mm']:.4f} mm")
    print(f"runtime: {grid['runtime_s']} -> {patch['runtime_s']} s")
    (OUT / "ab_geometry_policy.json").write_text(
        json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
