"""A/B the rail-node slope table: same forces, less time.

Runs the same short window twice -- once with ``VELCH_RAIL_SLOPE_TABLE=0`` (a fresh
central difference on the merged contact grid, the previous behaviour) and once with the
per-station table -- then compares the contact-force series sample by sample and reports
the wall clock from each manifest.

The numbers are asked for equality, not for closeness: substituting the interpolated
node slopes changes nothing at rail nodes and is the same linear blend at the wheel nodes
inserted between them.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "validation" / "crh380a_m" / "case_frog_N_strip05.json"
OUTPUTS = {
    "table": ROOT / "validation" / "crh380a_m" / "out_ab_slope_table",
    "fresh": ROOT / "validation" / "crh380a_m" / "out_ab_slope_fresh",
}


def run(name: str, use_table: bool) -> dict:
    env = dict(os.environ)
    env["VELCH_RAIL_SLOPE_TABLE"] = "1" if use_table else "0"
    output = OUTPUTS[name]
    command = [sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle",
               str(CASE), "--output", str(output)]
    started = time.perf_counter()
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    wall = time.perf_counter() - started
    if result.returncode != 0:
        print(result.stdout[-2000:])
        print(result.stderr[-2000:])
        raise SystemExit(f"{name}: run failed with code {result.returncode}")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    summary = manifest.get("summary", {})
    return {"wall_s": wall, "nfev": summary.get("nfev"),
            "runtime_s": summary.get("wall_time_s") or summary.get("runtime_s"),
            "check": summary.get("numerically_checked"),
            "keys": sorted(summary)}


def read_forces(path: pathlib.Path) -> tuple[list[str], dict[str, list[float]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    columns: dict[str, list[float]] = {}
    for name in header:
        if name.endswith("_normal_n") and name.startswith("axle"):
            columns[name] = []
    for line in lines[1:]:
        if not line:
            continue
        fields = line.split(",")
        for name in columns:
            columns[name].append(float(fields[header.index(name)]))
    return header, columns


def main() -> int:
    summary = {}
    for name, use_table in (("fresh", False), ("table", True)):
        summary[name] = run(name, use_table)
        entry = summary[name]
        print(f"{name:6s} wall={entry['wall_s']:7.2f} s "
              f"nfev={entry['nfev']} checked={entry['check']}")
    print("manifest keys:", summary["fresh"]["keys"])

    _header, fresh = read_forces(OUTPUTS["fresh"] / "history.csv")
    _header, table = read_forces(OUTPUTS["table"] / "history.csv")
    if not fresh:
        print("no per-contact force columns found; dumping the header for inspection:")
        print(_header)
        return 1
    worst = 0.0
    bitwise = True
    for name in fresh:
        a, b = fresh[name], table[name]
        assert len(a) == len(b), f"{name}: sample count differs"
        delta = max((abs(x - y) for x, y in zip(a, b)), default=0.0)
        worst = max(worst, delta)
        bitwise = bitwise and a == b
    speedup = summary["fresh"]["wall_s"] / summary["table"]["wall_s"]
    print(f"columns={len(fresh)} samples={len(next(iter(fresh.values())))} "
          f"max|dN|={worst:.3e} N identical={bitwise} speedup={speedup:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
