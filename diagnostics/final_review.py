"""Read-only audit of a Velch run, diagnostics, and optional real PRR input."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from velch.profiles import load_profile  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prr", type=Path, help="optional real rail PRR for read-only parsing")
    args = parser.parse_args()
    output = ROOT / "examples" / "synthetic_transfer" / "output"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    summary = manifest["summary"]
    checks = {
        "run_numerically_checked": summary["result_status"] == "numerically_checked",
        "all_run_gates": all(summary["gates"].values()),
        "case_snapshot_hash": sha256(output / "case_snapshot.json") == manifest["case_sha256"],
        "profile_hashes": all(sha256(Path(path)) == digest for path, digest in
                              manifest["profile_asset_sha256"].items()),
    }
    history = output / "history.csv"
    with history.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    case = json.loads((output / "case_snapshot.json").read_text(encoding="utf-8"))
    expected = 1 + math.ceil(case["run"]["duration_s"] / case["run"]["output_step_s"])
    checks["history_rows"] = len(rows) == expected
    checks["history_finite"] = bool(rows) and all(
        math.isfinite(float(value)) for row in rows for value in row.values()
    )
    checks["nonnegative_penetration"] = all(
        float(value) >= 0 for row in rows for key, value in row.items()
        if key.endswith("_penetration_m")
    )
    for name in ("step_convergence", "static_energy_probe"):
        data = json.loads((ROOT / "diagnostics" / f"{name}.json").read_text(encoding="utf-8"))
        checks[name] = data["passed"] is True
    wheel = ROOT / "dist" / "velch_turnout_dynamics-0.2.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel) as archive:
        checks["wheel_package_contents"] = all(
            f"velch/{name}.py" in archive.namelist()
            for name in ("contact", "model", "profiles", "solver", "vehicle", "vehicle_solver", "cli")
        )
    real_prr = None
    if args.prr:
        profile = load_profile(args.prr, file_format="prr", surface="rail_top")
        real_prr = {"path": str(args.prr.resolve()), "sha256": profile.source_sha256,
                    "unique_y_points": len(profile.y_m),
                    "collapsed_points": profile.collapsed_points}
        checks["real_prr_read"] = len(profile.y_m) >= 3
    v2_output = ROOT / "examples" / "vehicle_v2" / "output"
    v2_manifest = json.loads((v2_output / "manifest.json").read_text(encoding="utf-8"))
    v2_case = json.loads((v2_output / "case_snapshot.json").read_text(encoding="utf-8"))
    with (v2_output / "history.csv").open(newline="", encoding="utf-8") as stream:
        v2_rows = list(csv.DictReader(stream))
    checks["v2_run_gates"] = (v2_manifest["summary"]["result_status"] == "numerically_checked"
                              and all(v2_manifest["summary"]["gates"].values()))
    checks["v2_input_hashes"] = (sha256(v2_output / "case_snapshot.json") == v2_manifest["case_sha256"]
                                  and all(sha256(Path(path)) == digest for path, digest in
                                          v2_manifest["profile_asset_sha256"].items()))
    checks["v2_history_rows"] = len(v2_rows) == 1 + math.ceil(
        v2_case["run"]["duration_s"] / v2_case["run"]["output_step_s"])
    checks["v2_history_finite"] = bool(v2_rows) and all(
        math.isfinite(float(value)) for row in v2_rows for value in row.values())
    checks["v2_nonnegative_penetration"] = all(
        float(value) >= 0 for row in v2_rows for key, value in row.items()
        if key.endswith("_penetration_m"))
    checks["v2_numerical_probes"] = json.loads(
        (ROOT / "diagnostics" / "vehicle_v2_checks.json").read_text(encoding="utf-8"))["passed"]
    checks["simpack_topology_read_only"] = json.loads(
        (ROOT / "diagnostics" / "simpack_vehicle_topology_evidence.json").read_text(encoding="utf-8"))["passed"]
    report = {"software": "Velch 0.2.0", "checks": checks, "passed": all(checks.values()),
              "history_rows": len(rows), "wheel_file": str(wheel.resolve()),
              "vehicle_v2_history_rows": len(v2_rows),
              "real_prr": real_prr,
              "physics_validation_status": summary["physics_validation_status"]}
    target = ROOT / "diagnostics" / "final_review.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
