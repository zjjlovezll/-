"""One high-mode-count data point: push the modal track to the mesh limit.

Uses a finer beam mesh (element 0.1 m over 150 m -> 1502 elements) so up to
~3000 modes exist, then keeps every available mode.  This is the closest
measured stand-in for SDITT's 6204 retained modes.
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


modes = BASE / "modes_scale_high.json"
print("building modes (element 0.1 m) ...", flush=True)
build_s = run(
    "validation/crh380a_m/build_rail_modes.py",
    "--length", "150", "--element", "0.1",
    "--max-hz", "2000000", "--limit", "6000",
    "--out", str(modes),
)
payload = json.loads(modes.read_text(encoding="utf-8"))
freqs = [float(mode["frequency_hz"]) for mode in payload["modes"]]
print(f"modes={len(freqs)} f_max={freqs[-1]:.0f} Hz build={build_s:.1f} s", flush=True)

case = BASE / "case_scale_high_0p05s.json"
run(
    "validation/crh380a_m/make_modal_variant.py",
    "--modal-file", modes.name,
    str(SOURCE), str(case),
)
out = BASE / "out_scale_high"
print("running ...", flush=True)
wall = run("-m", "velch", "run-vehicle", str(case), "--output", str(out))
summary = json.loads((out / "manifest.json").read_text(encoding="utf-8"))["summary"]
solver = summary.get("solver") or {}
nfev = solver.get("nfev")
record = {
    "modes": len(freqs),
    "f_max_hz": round(freqs[-1], 1),
    "build_s": round(build_s, 1),
    "dof": summary["total_dof"],
    "track_dof": summary["track_dof"],
    "nfev": nfev,
    "peak_kn": max(summary["peak_normal_force_n"].values()) / 1e3,
    "penetration_um": summary["max_penetration_m"] * 1e6,
    "wall_s": round(wall, 1),
    "us_per_rhs": round(1e6 * wall / nfev, 0) if nfev else None,
    "gates_all_true": all(summary["gates"].values()),
}
print(json.dumps(record, indent=2, ensure_ascii=False))
(BASE / "mode_scaling_high.json").write_text(
    json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
)
