"""Round 72: does the seat really see a straight rail on the geometry route?"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\src")

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _placement_enabled, _seat

WORK = Path(r"F:\velch_tmp\curve72")


def main() -> int:
    case = load_vehicle_case(WORK / "curved_geom.json")
    dynamics = VehicleDynamics(case, contact_workers=1)
    q = np.asarray(case.initial_q, dtype=float)
    v = np.zeros(dynamics.dimension)
    speed = float(case.vehicle.travel_speed_m_s)

    def rail_y(label: str) -> None:
        index = 0
        x_m = float(case.run.x_start_m) + float(case.vehicle.axle_offsets_m[0])
        state = dynamics.track.local_state(q[dynamics.dof:], v[dynamics.dof:], index, x_m, speed)
        print(f"  {label:22s} x_m {x_m:6.2f}  rail y {float(state[0]):+.6f}  vy {float(state[2]):+.6f}"
              f"  placement {'on' if dynamics.track.placement else 'off'}"
              f"  enabled {dynamics.placement_enabled}")

    print("placement route:", _placement_enabled(case.run))
    rail_y("before _seat")
    try:
        _seat(case, dynamics, q, v)
    except Exception as error:  # noqa: BLE001
        print(f"  _seat raised {type(error).__name__}: {str(error)[:90]}")
    rail_y("after _seat")
    print("settled dynamics placement restored:", dynamics.track.placement is not None,
          "enabled:", dynamics.placement_enabled)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
