"""Wall clock of recorded runs, for the speed bookkeeping in SPEED_2026-10-20.md."""

from __future__ import annotations

import json
import sys
from pathlib import Path

for name in sys.argv[1:]:
    path = Path(name, "manifest.json")
    if not path.exists():
        print(f"{name:<22} (no manifest)")
        continue
    manifest = json.loads(path.read_text(encoding="utf-8"))
    summary = manifest.get("summary", {})
    wall = manifest.get("elapsed_wall_s")
    nfev = summary.get("function_evaluations")
    print(f"{name:<22} wall {wall:8.2f} s   nfev {nfev:>8}   "
          f"status {summary.get('result_status')}")
