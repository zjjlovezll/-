"""Prescribe the curving attitude at t=0 so the static solver does not fight the path.

The 35-DOF vehicle has a single lateral state per body, while the path gives each wheelset its own
lateral position.  Forcing four wheelsets 20 m apart onto a 1100 m curve therefore starts the model in
a 350 mm lateral distortion, which rolls the bogies and unloads one rail (the "hung bogie" failure).
Setting every body's lateral state to the path value at its own station removes that initial
distortion; steering forces still develop later, which is what we want to see.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402


def main(source: str, target: str) -> int:
    raw = json.loads((HERE / source).read_text(encoding="utf-8"))
    case = load_vehicle_case(HERE / source)
    lateral_x = [case.run.x_start_m + offset for offset in case.vehicle.axle_offsets_m]
    bogie_x = [0.5 * (lateral_x[i] + lateral_x[i + 1]) for i in (0, 2)]
    carbody_x = 0.5 * (lateral_x[0] + lateral_x[-1])

    q = list(raw.get("initial_state", {}).get("q") or case.initial_q)
    # Keep every entry the window case already solved for: only the lateral states are prescribed.
    # (Zeroing the compliant-track rail DOFs here silently pushed the wheelsets ~15 mm below the
    # crown and made the left rail report no contact at all.)
    for axle, station in enumerate(lateral_x):
        q[5 * axle] = case.path.at(station)
    for bogie, station in enumerate(bogie_x):
        q[20 + 5 * bogie] = case.path.at(station)
    q[30] = case.path.at(carbody_x)

    raw.setdefault("initial_state", {})["q"] = q
    (HERE / target).write_text(json.dumps(raw, indent=1), encoding="utf-8")
    print(f"wrote {target}")
    for label, station, value in (("axle1", lateral_x[0], q[0]), ("axle4", lateral_x[-1], q[15]),
                                  ("carbody", carbody_x, q[30])):
        print(f"  {label:<8} x = {station:8.3f} m   q_y = {value * 1e3:8.2f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
