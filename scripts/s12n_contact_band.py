"""Round 42: which band does the contact pick on a canted, curved rail?"""

import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\src")

import velch.vehicle_solver as vs
from velch.contact_search import _absolute_arrays
from velch.vehicle import load_vehicle_case

BASE = pathlib.Path("F:/velch_tmp/curve_frames/case_r1100_geometry.json")
WORK = pathlib.Path("F:/velch_tmp/curve42")
WORK.mkdir(parents=True, exist_ok=True)

raw = json.loads(BASE.read_text(encoding="utf-8"))
raw["case_id"] = "probe42"
raw["run"].update({"curve_radius_m": 1100.0, "curve_cant_m": 0.107, "curve_geometry": True,
                   "align_to_track": True, "x_start_m": 60.0, "duration_s": 0.01,
                   "output_step_s": 0.005})
raw.setdefault("vehicle", {})["travel_speed_m_s"] = 100.0 / 3.6
raw.pop("initial_state", None)
path = WORK / "case42.json"
path.write_text(json.dumps(raw, indent=1), encoding="utf-8")

case = load_vehicle_case(path)
dynamics = vs.VehicleDynamics(case)
q = vs._place_on_alignment(case, dynamics, np.zeros(dynamics.dimension))
v = np.zeros(dynamics.dimension)

# Lift the four wheelsets clear of the rail so nothing is deep in penetration, then evaluate
# the *search* only (no Newton): what does it pick when the crown is 54 mm up and tilted?
for axle in range(4):
    wid = dynamics.topology.wheelset_id(axle)
    q[dynamics.topology.require(wid, "z")] = float(case.vehicle.wheel_center_height_m)

force, _ = dynamics.evaluate(0.0, q, v)
print(f"max |force| {float(np.max(np.abs(force))):.3e} N\n")

for rail_id, responses in dynamics.body_contacts.items():
    for response in responses:
        geometry = getattr(response, "geometry", None)
        if geometry is None:
            continue
        print(f"{rail_id:22s} penetration {geometry.penetration_m * 1e3:+8.3f} mm "
              f"lever_y {geometry.lever_y_m * 1e3:+8.3f} mm "
              f"lever_z {geometry.lever_z_m * 1e3:+8.3f} mm "
              f"N {response.wheel_force_z_n / 1e3:8.2f} kN")

print("\nwheel band vs rail band on the left rail of axle 1:")
rail = next(item for item in case.rails if "axle1" in str(item.id) and "left" in str(item.id))
bodies = getattr(rail, "contact_bodies", None) or getattr(rail, "bodies", None)
sample = (bodies[0].series if bodies else rail.profiles).sample(70.0, 1)
offset = -abs(float(case.wheels[0].lateral_offset_m))
arrays = _absolute_arrays(case.wheels[0].profile, sample, wheel_y_m=0.045455, wheel_z_m=0.43,
                          wheel_roll_rad=0.071729, wheel_lateral_offset_m=offset,
                          rail_y_m=0.0, rail_z_m=0.0)
wy, wz = arrays[0], arrays[1]
print(f"  wheel y {float(np.min(wy)) * 1e3:+.1f} .. {float(np.max(wy)) * 1e3:+.1f} mm")
print(f"  rail  y {float(np.min(sample.profile.y_m)) * 1e3:+.1f} .. "
      f"{float(np.max(sample.profile.y_m)) * 1e3:+.1f} mm, top {float(np.max(sample.profile.z_m)) * 1e3:+.3f} mm")
inside = (wy >= float(np.min(sample.profile.y_m))) & (wy <= float(np.max(sample.profile.y_m)))
print(f"  wheel points inside the rail band: {int(np.count_nonzero(inside))} of {wy.size}")
