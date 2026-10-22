"""A1: run the same frog case with geometry_policy grid vs spline and compare.

The spline policy only relocates the contact point, so the two runs must differ in
nothing but the event: same DOF count, same step count is *not* required (the event
moves), but the force history must stay inside the same gates and the peak must move
by a physically explainable amount.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SOURCE = HERE / "case_frog_N_strip05.json"
WORK = BASE / ".tmp" / "a1_spline"

COLUMNS = ("axle1_right_normal_n", "axle1_left_normal_n")


def build_variant(policy: str) -> Path:
    case = json.loads(SOURCE.read_text(encoding="utf-8"))
    contact = case.setdefault("contact", {})
    contact["geometry_policy"] = policy
    # The case's asset paths are relative to the case file, so the variant has to sit
    # beside the original -- a copy under .tmp loses bodies/*.csv and fails at load.
    target = HERE / f"case_frog_a1_{policy}.json"
    target.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def run(case_path: Path, tag: str) -> dict:
    output = WORK / f"out_{tag}"
    if output.exists():
        shutil.rmtree(output)
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle",
         str(case_path), "--output", str(output)],
        cwd=str(BASE), capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"{tag} failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    summary = manifest.get("summary", {})
    history = output / "history.csv"
    header = history.read_text(encoding="utf-8").splitlines()[0].split(",")
    peaks = {}
    for name in COLUMNS:
        if name not in header:
            continue
        index = header.index(name)
        values = [float(line.split(",")[index])
                  for line in history.read_text(encoding="utf-8").splitlines()[1:]]
        peaks[name] = (max(values), min(values), sum(1 for v in values if v <= 0.0),
                       len(values))
    return {"summary": summary, "peaks": peaks}


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"missing case {SOURCE.name}")
    report = {}
    made = []
    for policy in ("grid", "spline"):
        case_path = build_variant(policy)
        made.append(case_path)
        report[policy] = run(case_path, policy)
        print(f"{policy}: done")
    for path in made:
        path.unlink(missing_ok=True)
    for policy, data in report.items():
        summary = data["summary"]
        peak = data["peaks"].get("axle1_right_normal_n")
        print(f"  {policy:>6}: peak {peak[0]:12.1f} N  min {peak[1]:10.1f} N  "
              f"zero {peak[2]}/{peak[3]}  nfev {summary.get('nfev')}  "
              f"max_pen {summary.get('max_penetration_m')}")
    grid = report["grid"]["peaks"]["axle1_right_normal_n"]
    spline = report["spline"]["peaks"]["axle1_right_normal_n"]
    if grid[0]:
        print(f"  peak change {100.0 * (spline[0] - grid[0]) / grid[0]:+.2f} %")
    print(f"  artefacts under {WORK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
