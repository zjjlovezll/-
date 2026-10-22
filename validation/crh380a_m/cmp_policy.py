"""Compare the policy A/B runs: peak force, penetration, contact coverage, cost."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out_pol"


def read_history(path: Path) -> dict[str, np.ndarray]:
    data = np.genfromtxt(path, delimiter=",", names=True)
    return {name: data[name] for name in data.dtype.names}


def main() -> None:
    rows = []
    for folder in sorted(OUT.iterdir()):
        manifest = folder / "manifest.json"
        if not manifest.exists():
            continue
        summary = json.loads(manifest.read_text(encoding="utf-8"))["summary"]
        peaks = summary["peak_normal_force_n"]
        active = summary["active_output_samples"]
        history = read_history(folder / "history.csv")
        right = history["axle1_right_normal_n"]
        z = history["axle1_z_m"]
        rows.append(dict(
            case=folder.name.replace("case_pol_", ""),
            peak_right_kN=peaks["axle1_right"] / 1e3,
            peak_right2_kN=peaks["axle2_right"] / 1e3,
            mean_right_kN=float(np.mean(right)) / 1e3,
            max_pen_mm=summary["max_penetration_m"] * 1e3,
            active_right=active["axle1_right"],
            z_span_mm=float(np.ptp(z)) * 1e3,
            nfev=summary["solver"]["nfev"],
            wall_s=summary["solver"].get("wall_s"),
            status=summary["result_status"],
        ))
    rows.sort(key=lambda r: r["peak_right_kN"])
    header = (f"{'case':<18}{'R1 peak':>9}{'R2 peak':>9}{'R1 mean':>9}"
              f"{'maxpen':>9}{'contact':>9}{'z span':>8}{'nfev':>8}{'wall':>7}  status")
    print(header)
    print("-" * len(header))
    for r in rows:
        wall = f"{r['wall_s']:.0f}s" if r["wall_s"] else "-"
        print(f"{r['case']:<18}{r['peak_right_kN']:>9.1f}{r['peak_right2_kN']:>9.1f}"
              f"{r['mean_right_kN']:>9.1f}{r['max_pen_mm']:>9.3f}{r['active_right']:>6}/101"
              f"{r['z_span_mm']:>8.3f}{r['nfev']:>8}{wall:>7}  {r['status']}")


if __name__ == "__main__":
    sys.exit(main())
