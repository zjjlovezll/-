"""Sweep the wing-rail lift amplitude (the 60TY1 calibration knob).

Score for each amplitude: front axle right peak normal force, lost contact
samples, max penetration.  Reference (Simpack, same window): peak ~128 kN,
0 lost samples, max penetration 0.433 mm.

Usage: python sweep_wing_rise.py [case_I_wing.json]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]

AMPLITUDES_MM = (0.0, 0.3, 0.5, 0.8, 1.2)


def main(argv: list[str]) -> int:
    base_case = Path(argv[1]) if len(argv) > 1 else BASE / "case_I_wing.json"
    print(f"base {base_case.name}  wing lift sweep (mm) {AMPLITUDES_MM}")
    print(f"  {'h_mm':>6s} {'R1_kN':>8s} {'lost':>5s} {'R2_kN':>8s} {'lost2':>6s} "
          f"{'max_pen_mm':>11s} {'nfev':>7s}")
    for h_mm in AMPLITUDES_MM:
        tag = f"rise{h_mm:.1f}".replace(".", "p")
        case_path = BASE / f"case_K_{tag}.json"
        subprocess.run(
            [sys.executable, "-X", "utf8", str(BASE / "make_wing_rise.py"),
             str(base_case), str(case_path), f"{h_mm:.3f}"],
            cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
        )
        subprocess.run(
            [sys.executable, "-X", "utf8", str(BASE / "make_window_case.py"),
             case_path.name, "frog", "69.0"],
            cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
        )
        window = BASE / f"case_frog_K_{tag}_0p05s.json"
        out = BASE / f"out_K_{tag}"
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(window),
             "--output", str(out)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        manifest = out / "manifest.json"
        if not manifest.exists():
            print(f"  {h_mm:6.1f}   FAILED {proc.stderr.strip().splitlines()[-1:]}")
            continue
        summary = json.loads(manifest.read_text(encoding="utf-8"))["summary"]
        peaks = summary["peak_normal_force_n"]
        active = summary["active_output_samples"]
        total = active["axle1_left"]
        print(f"  {h_mm:6.1f} {peaks['axle1_right'] / 1e3:8.1f} "
              f"{total - active['axle1_right']:5d} {peaks['axle2_right'] / 1e3:8.1f} "
              f"{total - active['axle2_right']:6d} "
              f"{summary['max_penetration_m'] * 1e3:11.4f} {summary['solver']['nfev']:7d}"
              f"  {summary['result_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
