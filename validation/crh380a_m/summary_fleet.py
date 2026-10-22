"""Summarise the theta fleet: fastener k_z/c_z scale -> frog-window peak force.

Reads manifests with json (never ConvertFrom-Json in PowerShell: asset_hashes contain
backslashes that break the parser and dump 200 KB to the console).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOTS = [
    Path(r"F:\velch_tmp\fleet"),
    Path(__file__).resolve().parent,
]

print(f"{'case':<28}{'peak_R_kN':>10}{'min_R_kN':>10}{'lost':>6}{'status':>22}")
for root in ROOTS:
    if not root.exists():
        continue
    for path in sorted(root.glob("fleet_*/manifest.json")):
        summary = json.loads(path.read_text(encoding="utf-8"))["summary"]
        peak = summary["peak_normal_force_n"]["axle1_right"] / 1e3
        active = summary["active_output_samples"]["axle1_right"]
        total = summary.get("rail_patch_count")
        lost = summary["gates"]["solver_completed"]
        print(f"{path.parent.name:<28}{peak:>10.1f}{0.0:>10.1f}"
              f"{active:>6}{summary['result_status']:>22}")
