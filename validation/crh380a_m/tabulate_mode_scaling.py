"""Tabulate the mode-count scaling results from the run manifests.

Wall times were measured by ``run_mode_scaling.py`` (subprocess wall clock,
including interpreter start-up) and are carried here verbatim.
"""

from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
WALL = {60: 58.48, 160: 63.68, 320: 66.91, 640: 88.86, 1280: 106.31}
F_MAX = {60: 243.2, 160: 633.9, 320: 2402.2, 640: 9865.1, 1280: 19993.3}

table = []
for modes, wall in WALL.items():
    summary = json.loads(
        (BASE / f"out_scale_{modes}" / "manifest.json").read_text(encoding="utf-8")
    )["summary"]
    solver = summary.get("solver") or {}
    nfev = solver.get("nfev")
    table.append(
        {
            "modes": modes,
            "dof": summary["total_dof"],
            "track_dof": summary["track_dof"],
            "nfev": nfev,
            "peak_kn": max(summary["peak_normal_force_n"].values()) / 1e3,
            "penetration_um": summary["max_penetration_m"] * 1e6,
            "wall_s": wall,
            "f_max_hz": F_MAX[modes],
            "us_per_rhs": (1e6 * wall / nfev) if nfev else None,
        }
    )

print(
    f"{'modes':>6} {'dof':>5} {'nfev':>7} {'peak kN':>8} {'pen um':>7} "
    f"{'wall s':>7} {'fmax Hz':>9} {'us/RHS':>7}"
)
for row in table:
    print(
        f"{row['modes']:>6} {row['dof']:>5} {row['nfev']:>7} "
        f"{row['peak_kn']:>8.1f} {row['penetration_um']:>7.1f} "
        f"{row['wall_s']:>7.1f} {row['f_max_hz']:>9.0f} {row['us_per_rhs']:>7.0f}"
    )

(BASE / "mode_scaling_table.json").write_text(json.dumps(table, indent=2), encoding="utf-8")
