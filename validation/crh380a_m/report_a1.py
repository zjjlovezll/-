"""Read the A1 strip-window runs straight from their manifests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    header = f"{'case':16s} {'peak kN':>9s} {'min kN':>8s} {'zero':>5s} {'maxpen mm':>10s} {'dE J':>9s}  gates"
    print(header)
    for output in sorted(BASE.glob("out_a1_*")):
        manifest = output / "manifest.json"
        if not manifest.is_file():
            continue
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        summary = payload["summary"]
        table_path = output / "history.csv"
        peak = low = float("nan")
        zeros = -1
        if table_path.is_file():
            table = np.genfromtxt(table_path, delimiter=",", names=True)
            force = np.asarray(table["axle1_right_normal_n"], dtype=float)
            peak, low = float(force.max()) / 1e3, float(force.min()) / 1e3
            zeros = int(np.count_nonzero(force <= 1.0))
        gates = summary.get("gates", {})
        failed = [name for name, value in gates.items() if not value]
        penetration = summary.get("max_penetration_m")
        energy = summary.get("energy_change_j")
        print(
            f"{output.name[7:]:16s} {peak:9.3f} {low:8.3f} {zeros:5d}"
            f" {penetration * 1e3 if penetration is not None else float('nan'):10.4f}"
            f" {energy:9.1f}  {'PASS' if not failed else 'FAIL ' + ','.join(failed)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
