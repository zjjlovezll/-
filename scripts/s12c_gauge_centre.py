"""Print the gauge centre the loader produced, and where the alignment puts the wheelsets.

Round 18: on the R = 1100 m geometry-route case only left-rail patches exist, with 5.5-17 mm
penetration, which is the signature of a vehicle standing ~45 mm beside rails that moved.
`_gauge_centre` reads the gauge centre off the *sampled* rails; `CurveSeries` shifts those samples.
If the centre comes back ~0 while the rails are shifted, the alignment is a no-op and the vehicle
stays where it was.

Run: python -X utf8 scripts/s12c_gauge_centre.py
"""

from __future__ import annotations

import json
import pathlib

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _align_to_track_frame, _gauge_centre

WORK = pathlib.Path(r"F:\velch_tmp\s12c")
RADIUS_M = 1100.0
X_START_M = 60.0


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
    case = load_vehicle_case(build())
    print(f"rails {len(case.rails)}  first rail id {case.rails[0].id}")
    bodies = getattr(case.rails[0], "bodies", ())
    print(f"series type {type(bodies[0].series).__name__ if bodies else 'no bodies'}")
    for s_m in (60.0, 70.0, 80.0):
        centre, tangent = _gauge_centre(case, s_m)
        print(f"  gauge centre at {s_m:5.1f} m: {centre:+.6f} m   tangent {tangent:+.6e}")
        # what the sampled rails say on each side
        for rail in case.rails[:2]:
            samples = getattr(rail, "bodies", ())
            if not samples:
                continue
            profile = samples[0].series.sample(s_m, 1).profile
            print(f"    {rail.id:>28}: mean y_m {profile.y_m.mean():+.6f}  "
                  f"span [{profile.y_m.min():+.4f}, {profile.y_m.max():+.4f}]")
    dynamics = VehicleDynamics(case)
    q = _align_to_track_frame(case, dynamics, [0.0] * dynamics.dimension)
    for axle in (1, 2, 3, 4):
        y = q[dynamics.topology.require(f"wheelset{axle}", "y")]
        print(f"  after alignment wheelset{axle}.y = {y:+.6f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
