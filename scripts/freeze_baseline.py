"""Freeze a time-history baseline, because the only oracle we have is static.

`tests/test_oracle_frozen.py` pins the static seat (59 680.577 N, -65.47 µm) and nothing
else.  That is not enough to prove that adding a speed profile leaves the dynamics alone:
the acceptance the architecture review asks for is **the same bytes**, three cases, before
and after.  So this script records the sha256 of `history.csv` for a few short cases, and
`--check` re-runs them and fails on any drift.

Two deliberate limits, both stated on the JSON itself:

* the hashes are for **this build of numpy/scipy**; a different BLAS may sum the same
  numbers in a different order, so a cross-machine mismatch is information, not a verdict;
* the durations are shortened from the declared ones to keep the check to seconds.  A
  short case exercises the same right-hand side, not the same trajectory.

Usage:
    python -X utf8 scripts/freeze_baseline.py            # write or refresh the baseline
    python -X utf8 scripts/freeze_baseline.py --check    # re-run and compare, exit 2 on drift
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
BASELINE = REPO / "docs" / "baselines" / "time_history.json"

#: (label, case path relative to the repository, duration override in seconds)
CASES: tuple[tuple[str, str, float], ...] = (
    ("straight_rigid", "examples/vehicle_v2/case.json", 0.020),
    ("straight_flexible", "examples/vehicle_v2/case.json", 0.020),
)



def _absolute(node, base: Path) -> None:
    """A derived case lives elsewhere, so its relative profile names must become absolute."""

    for item in node.get("wheels", []):
        spec = item.get("profile") or {}
        if "file" in spec and not Path(spec["file"]).is_absolute():
            spec["file"] = str((base / spec["file"]).resolve())
    for template in node.get("rail_templates", []):
        for station in template.get("stations", []):
            spec = station.get("profile") or {}
            if "file" in spec and not Path(spec["file"]).is_absolute():
                spec["file"] = str((base / spec["file"]).resolve())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(case_path: Path, duration_s: float, flexible: bool, output: Path) -> dict:
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

    raw = json.loads(case_path.read_text(encoding="utf-8"))
    _absolute(raw, case_path.parent)
    raw["run"]["duration_s"] = duration_s
    raw["run"]["method"] = "BDF" if flexible else "DOP853"
    if flexible:
        raw["run"]["jacobian"] = "analytic"
        raw["flexible_wheelset"] = {"source": "table-2-3", "axles": [1, 2, 3, 4], "radius_m": 0.46}
    objective = output / "case_used.json"
    output.mkdir(parents=True, exist_ok=True)
    objective.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

    loaded = load_vehicle_case(objective)
    started = time.perf_counter()
    result = simulate_vehicle(loaded)
    elapsed = time.perf_counter() - started
    history_path, manifest_path = save_vehicle_result(loaded, result, output)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    return {
        "coordinates": int(loaded.state_layout.dimension if hasattr(loaded, "state_layout") else 0),
        "duration_s": duration_s,
        "seconds": round(elapsed, 3),
        "history_sha256": _sha256(Path(history_path)),
        "history_bytes": Path(history_path).stat().st_size,
        "result_status": manifest["summary"]["result_status"],
        "gates": {name: bool(value) for name, value in manifest["summary"]["gates"].items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(r"F:\velch_tmp\baseline"))
    options = parser.parse_args()

    source = json.loads((REPO / CASES[0][1]).read_text(encoding="utf-8"))
    entries = {}
    for label, relative, duration in CASES:
        flexible = label.endswith("flexible")
        case_path = REPO / relative
        entries[label] = _run(case_path, duration, flexible, options.output / label)
        print(f"{label:18} {entries[label]['result_status']:22} "
              f"{entries[label]['seconds']:7.1f} s  {entries[label]['history_sha256'][:16]}")

    payload = {
        "note": (
            "sha256 of history.csv for short cases; same-build comparison only.  A different "
            "numpy/BLAS may reorder the same sums, so a cross-machine mismatch is information, "
            "not a verdict.  Durations are shortened to keep the check to seconds."
        ),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": _scipy_version(),
            "platform": platform.platform(),
        },
        "cases": entries,
    }

    if not options.check:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwritten {BASELINE.relative_to(REPO)}")
        return 0

    if not BASELINE.exists():
        print(f"no baseline at {BASELINE}")
        return 2
    stored = json.loads(BASELINE.read_text(encoding="utf-8"))
    drift = []
    for label, entry in entries.items():
        old = stored["cases"].get(label)
        if old is None:
            drift.append(f"{label}: missing from the baseline")
        elif old["history_sha256"] != entry["history_sha256"]:
            drift.append(
                f"{label}: {old['history_sha256'][:16]} -> {entry['history_sha256'][:16]}"
            )
        elif old["result_status"] != entry["result_status"]:
            drift.append(f"{label}: status {old['result_status']} -> {entry['result_status']}")
    if drift:
        print("\nDRIFT")
        for line in drift:
            print("  " + line)
        return 2
    print("\nVERDICT: UNCHANGED")
    return 0


def _scipy_version() -> str:
    try:
        import scipy
    except ImportError:  # pragma: no cover - scipy is a hard dependency
        return "missing"
    return scipy.__version__


if __name__ == "__main__":
    raise SystemExit(main())
