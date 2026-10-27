import json, pathlib, sys
sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\src")
from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _place_on_alignment, _body_offset_m

base = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
base["run"].update({"x_start_m": 60.0, "duration_s": 0.01, "output_step_s": 0.01,
                    "curve_radius_m": 1100.0, "curve_cant_m": 0.107, "curve_geometry": True})
base["vehicle"]["travel_speed_m_s"] = 100.0 / 3.6
base.pop("initial_state", None)
p = pathlib.Path(r"F:\velch_tmp\where_place.json")
p.write_text(json.dumps(base, indent=1, ensure_ascii=False), encoding="utf-8")

case = load_vehicle_case(p)
dyn = VehicleDynamics(case)
q = import_array = __import__("numpy").array(case.initial_q, dtype=float)
v = __import__("numpy").array(case.initial_v, dtype=float)
placed = _place_on_alignment(case, dyn, q)
placement = dyn._curve_placement()
start = float(case.run.x_start_m)
print("rail             x_m   railDy(mm)  railY(mm)  bodyOffset   wheelDy(mm)")
for i, rail in enumerate(case.rails):
    x_m = start + case.vehicle.axle_offsets_m[rail.axle_index]
    dy, dz, dyds = placement(i, x_m)
    rail_y = dyn.track.local_state(placed, v, i, x_m, case.vehicle.travel_speed_m_s)[0]
    body = dyn.topology.wheelset_id(rail.axle_index)
    wheel_y = float(placed[dyn.topology.require(body, "y")])
    s_body = _body_offset_m(case, dyn.topology, dyn.topology.bodies[dyn.topology.offset(body) and 0] if False else next(b for b in dyn.topology.bodies if b.id == body), placed)
    print(f"{rail.id:16s} {x_m:6.2f} {dy*1000:10.3f} {rail_y*1000:10.3f} {s_body:10.3f} {wheel_y*1000:10.3f}")
