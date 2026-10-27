"""Mileage closure and a three-leg archive baseline.

The goal's third acceptance item asks for a mileage closure of 0.2 % or better on a varying
speed.  This script measures it from the written `history.csv` rather than from the helper, so
it checks the artefact and not the function that produced it: the last frame's mileage column
must equal the analytic distance the schedule says the vehicle covered.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from velch.io.history import read_history  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle  # noqa: E402

WORK = pathlib.Path(r"F:\velch_tmp\speed_legs")
BASE = REPO / "examples" / "vehicle_v2" / "case.json"
DURATION_S = 0.05
LEGS = [
    {"speed_kmh": 80.0, "duration_s": 0.020},
    {"speed_kmh": 60.0, "duration_s": 0.015},
    {"speed_kmh": 40.0, "duration_s": 0.015},
]


def build() -> pathlib.Path:
    raw = json.loads(BASE.read_text(encoding="utf-8"))
    raw["run"]["duration_s"] = DURATION_S
    raw["run"]["speed_profile"] = {"legs": LEGS}
    base_dir = BASE.parent
    for item in raw.get("wheels", []):
        spec = item.get("profile") or {}
        if "file" in spec and not pathlib.Path(spec["file"]).is_absolute():
            spec["file"] = str((base_dir / spec["file"]).resolve())
    for template in raw.get("rail_templates", []):
        for station in template.get("stations", []):
            spec = station.get("profile") or {}
            if "file" in spec and not pathlib.Path(spec["file"]).is_absolute():
                spec["file"] = str((base_dir / spec["file"]).resolve())
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / "case_three_legs.json"
    path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return path


def main() -> int:
    case = load_vehicle_case(build())
    schedule = case.speed_schedule
    assert schedule is not None and not schedule.is_constant
    target = WORK / "out"
    result = simulate_vehicle(case)
    save_vehicle_result(case, result, target)
    table = read_history(target / "history.csv")
    times = np.asarray(table["time_s"], dtype=float)
    # The first axle's mileage column is the reference point plus that axle's offset.
    mileage = np.asarray(table["axle1_x_m"], dtype=float) - case.vehicle.axle_offsets_m[0]
    expected = case.run.x_start_m + schedule.x_at(float(times[-1]))
    closure = abs(mileage[-1] - expected) / max(abs(expected - case.run.x_start_m), 1e-9)
    # Independent check: integrate the schedule's own speed samples.
    integral = float(np.trapezoid([schedule.v_at(float(t)) for t in times], times))
    print(f"frames {len(times)}  status {result.summary['result_status']}")
    print(f"distance by schedule {schedule.distance_m:.9f} m, "
          f"by trapezoid {integral:.9f} m")
    print(f"mileage column end {mileage[-1]:.9f} m, expected {expected:.9f} m, "
          f"closure {closure:.3e}")
    print(f"spin gate {result.summary['gates'].get('spin_tracking')} "
          f"relative {result.summary.get('spin_tracking_relative')}")
    ok = closure <= 2.0e-3 and result.summary["gates"].get("spin_tracking") is True
    print("VERDICT:", "CLOSED" if ok else "FAILED")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
