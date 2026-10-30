"""Print the two arrays the strip contact actually compares, on a curved rail.

Round 20: shifting the rail surface by +45.5 mm gives 78 786 kN on the left rail with the vehicle
straight, and 150 690 kN once the vehicle is shifted by the same +45.5 mm -- two equal shifts should
cancel, so they are not in the same frame.  This probe prints `wheel_y` and `rail_y` bounds from the
real call, which is the only way to settle it.

Run: python -X utf8 scripts/s12f_contact_frames.py
"""

from __future__ import annotations

import json
import pathlib

import numpy as np

from velch import contact as contact_module
from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _align_to_track_frame

WORK = pathlib.Path(r"F:\velch_tmp\s12f")
RADIUS_M = 1100.0
X_START_M = 60.0

records: list[dict] = []
original = contact_module.find_strip_contact


def recording(*args, **kwargs):
    response = original(*args, **kwargs)
    if len(records) < 4:
        names = ("wheel_y", "wheel_z", "rail_y", "rail_z", "wheel_y_m", "wheel_z_m")
        bounds = {}
        for name, value in zip(names, args):
            array = np.asarray(value, dtype=float) if not np.isscalar(value) else None
            if array is not None and array.size:
                bounds[name] = (float(array.min()), float(array.max()), int(array.size))
        for name in names:
            if name in kwargs:
                array = np.asarray(kwargs[name], dtype=float)
                if array.size:
                    bounds[name] = (float(array.min()), float(array.max()), int(array.size))
        records.append(bounds)
    return response


def build() -> pathlib.Path:
    raw = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
    raw.pop("initial_state", None)
    raw["vehicle"]["travel_speed_m_s"] = 80.0 / 3.6
    raw["run"].update({"duration_s": 0.004, "output_step_s": 0.004, "x_start_m": X_START_M,
                       "curve_radius_m": RADIUS_M, "curve_cant_m": 0.0, "curve_geometry": True})
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / "case.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


def main() -> int:
    contact_module.find_strip_contact = recording  # type: ignore[assignment]
    case = load_vehicle_case(build())
    dynamics = VehicleDynamics(case)
    q = _align_to_track_frame(case, dynamics, [0.0] * dynamics.dimension)
    dynamics.evaluate(0.0, q, list(0.0 for _ in q))
    print(f"strip calls recorded: {len(records)}")
    for index, bounds in enumerate(records):
        print(f"  call {index}:")
        for name, (low, high, size) in bounds.items():
            print(f"    {name:>10}: [{low:+.6f}, {high:+.6f}]  n = {size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
