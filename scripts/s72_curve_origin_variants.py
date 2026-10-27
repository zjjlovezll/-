"""Round 71 probe: a run that starts on the straight lead and enters the curve."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\src")

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

WORK = Path(r"F:\velch_tmp\origin71")
CASES = (
    ("no_origin_30", {}),
    ("origin30_30", {"curve_origin_m": 30.0}),
    ("origin_tangent_30", {"curve_origin_m": 50.578}),
)


def build(name: str, extra: dict) -> Path:
    raw = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
    raw["run"].update({
        "curve_radius_m": 1100.0, "curve_geometry": True, "align_to_track": True,
        "duration_s": 0.02, "output_step_s": 0.01, "x_start_m": 30.0,
    })
    raw["run"].update(extra)
    raw["vehicle"]["travel_speed_m_s"] = 100.0 / 3.6
    raw.pop("initial_state", None)
    path = WORK / f"{name}.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    for name, extra in CASES:
        case = load_vehicle_case(build(name, extra))
        try:
            result = simulate_vehicle(case)
        except Exception as error:  # noqa: BLE001 - the message is the measurement
            print(f"{name:18s} FAILED {type(error).__name__}: {str(error)[:120]}")
            continue
        summary = result.summary
        failed = [gate for gate, ok in (summary.get("gates") or {}).items() if not ok]
        loads = summary.get("contact_peak_force_n") or {}
        shares = [float(value) / 59662.0 for value in loads.values()]
        print(f"{name:18s} {summary.get('result_status'):22s} failed={failed} "
              f"share={min(shares):.3f}..{max(shares):.3f}" if shares else
              f"{name:18s} {summary.get('result_status')} failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
