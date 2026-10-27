"""Round 41: does _absolute_arrays give the wheel its half of b*sin(phi)?"""

import json
import pathlib
import sys

import numpy as np

REPO = pathlib.Path("F:/ai道岔状态反演辨识/Velch")
sys.path.insert(0, str(REPO / "src"))

import velch.vehicle_solver as vs
from velch.contact_search import _absolute_arrays
from velch.vehicle import load_vehicle_case

BASE = pathlib.Path("F:/velch_tmp/curve_frames/case_r1100_geometry.json")
WORK = pathlib.Path("F:/velch_tmp/curve41")
WORK.mkdir(parents=True, exist_ok=True)

raw = json.loads(BASE.read_text(encoding="utf-8"))
raw["case_id"] = "probe41"
raw["run"].update({"curve_radius_m": 1100.0, "curve_cant_m": 0.107, "curve_geometry": True,
                   "align_to_track": True, "x_start_m": 60.0, "duration_s": 0.01,
                   "output_step_s": 0.005})
raw.setdefault("vehicle", {})["travel_speed_m_s"] = 100.0 / 3.6
raw.pop("initial_state", None)
path = WORK / "case41.json"
path.write_text(json.dumps(raw, indent=1), encoding="utf-8")

case = load_vehicle_case(path)
dynamics = vs.VehicleDynamics(case)
q = np.zeros(dynamics.dimension)
v = np.zeros(dynamics.dimension)
placed = vs._place_on_alignment(case, dynamics, q)

gauge = 2.0 * abs(float(case.wheels[0].lateral_offset_m))
theta = float(np.arcsin(0.107 / gauge))
print(f"theta {theta:+.6f} rad, b {gauge / 2:.4f} m, b sin(theta) {gauge / 2 * np.sin(theta) * 1e3:+.3f} mm")

axle = 0
x = float(case.run.x_start_m) + float(case.vehicle.axle_offsets_m[axle])
wid = dynamics.topology.wheelset_id(axle)
wheel_z = placed[dynamics.topology.require(wid, "z")]
wheel_y = placed[dynamics.topology.require(wid, "y")]
roll = placed[dynamics.topology.require(wid, "roll")]
print(f"wheelset{axle}: y {wheel_y * 1e3:+.3f} mm, z {wheel_z * 1e3:+.3f} mm, roll {roll:+.6f}")

profile = case.wheels[0].profile
for rail in case.rails:
    if f"axle{axle + 1}" not in str(rail.id):
        continue
    bodies = getattr(rail, "contact_bodies", None) or getattr(rail, "bodies", None)
    sample = (bodies[0].series if bodies else rail.profiles).sample(x, 1)
    side = +1.0 if "right" in str(rail.id) else -1.0
    offset = side * abs(float(case.wheels[0].lateral_offset_m))
    arrays = _absolute_arrays(profile, sample, wheel_y_m=wheel_y, wheel_z_m=wheel_z,
                             wheel_roll_rad=roll, wheel_lateral_offset_m=offset,
                             rail_y_m=0.0, rail_z_m=0.0)
    print(f"      arrays returns {type(arrays).__name__} of length {len(arrays)}")
    wy, wz = arrays[0], arrays[1]
    analytic = wheel_z + side * abs(float(case.wheels[0].lateral_offset_m)) * np.sin(roll) - 0.43
    print(f"  {str(rail.id):16s} side {side:+.0f} offset {offset * 1e3:+8.3f} mm")
    print(f"      wheel_z.min() {float(np.min(wz)) * 1e3:+9.3f} mm   (centre - R + tilt = {analytic * 1e3:+9.3f})")
    print(f"      rail_z.max()  {float(np.max(sample.profile.z_m)) * 1e3:+9.3f} mm"
          f"   wheel_y range {float(np.min(wy)) * 1e3:+.1f} .. {float(np.max(wy)) * 1e3:+.1f} mm")
