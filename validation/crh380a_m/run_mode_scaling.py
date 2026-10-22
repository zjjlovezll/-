"""Scaling: wall clock vs retained mode count, identical physical beam model.

All variants share one fine beam mesh (element 0.2 m) so the first N mode shapes
are identical; only the truncation index N changes.  This isolates the cost of
modal DOF, which is what a "same model as SDITT" comparison needs.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
VELCH = BASE.parents[1]
SOURCE = BASE / "case_frog_N_strip05.json"
POINTS = (60, 160, 320, 640, 1280)


def run(*args: str) -> float:
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-X", "utf8", *args],
        cwd=str(VELCH),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.perf_counter() - start
    if result.returncode != 0:
        print(result.stdout[-1500:])
        print(result.stderr[-2500:])
        raise SystemExit(f"failed: {' '.join(args)}")
    return elapsed


rows = []
for count in POINTS:
    modes = BASE / f"modes_scale_{count}.json"
    print(f"[{count}] building modes ...", flush=True)
    run(
        "validation/crh380a_m/build_rail_modes.py",
        "--length", "150", "--element", "0.2",
        "--max-hz", "20000", "--limit", str(count),
        "--out", str(modes),
    )
    payload = json.loads(modes.read_text(encoding="utf-8"))
    freqs = [float(mode["frequency_hz"]) for mode in payload["modes"]]
    case = BASE / f"case_scale_{count}_0p05s.json"
    run(
        "validation/crh380a_m/make_modal_variant.py",
        "--modal-file", modes.name,
        str(SOURCE), str(case),
    )
    out = BASE / f"out_scale_{count}"
    print(f"[{count}] running {case.name} ...", flush=True)
    wall = run("-m", "velch", "run-vehicle", str(case), "--output", str(out))
    summary = json.loads((out / "manifest.json").read_text(encoding="utf-8"))["summary"]
    rows.append(
        {
            "modes": count,
            "dof": summary.get("dof"),
            "nfev": summary.get("nfev"),
            "peak": summary.get("peak_normal_force_n"),
            "wall_s": round(wall, 2),
            "f_max": round(freqs[-1], 1),
            "us_per_rhs": round(1e6 * wall / max(1, summary.get("nfev", 1)), 1),
        }
    )
    print(rows[-1], flush=True)

print()
print(f"{'modes':>6} {'dof':>6} {'nfev':>7} {'peak kN':>9} {'wall s':>8} {'f_max Hz':>10} {'us/RHS':>8}")
for r in rows:
    print(
        f"{r['modes']:>6} {r['dof']:>6} {r['nfev']:>7} "
        f"{r['peak']/1e3 if r['peak'] else 0:>9.1f} {r['wall_s']:>8.1f} "
        f"{r['f_max']:>10.1f} {r['us_per_rhs']:>8.1f}"
    )

(BASE / "mode_scaling.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
