"""Round 38: with the rise published, which rail is 107 mm out?"""

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path("F:/ai道岔状态反演辨识/Velch")
SOLVER = REPO / "src" / "velch" / "vehicle_solver.py"

text = SOLVER.read_text(encoding="utf-8")
patched = text.replace("        rise = abs(0.5 * gauge * math.sin(theta))\n        rise = 0.0",
                       "        rise = abs(0.5 * gauge * math.sin(theta))", 1)
if patched == text:
    raise SystemExit("rise anchor missing")
SOLVER.write_text(patched, encoding="utf-8", newline="")

try:
    sys.path.insert(0, str(REPO / "src"))
    import numpy as np

    import velch.vehicle_solver as vs
    from velch.vehicle import load_vehicle_case

    base = pathlib.Path("F:/velch_tmp/curve_frames/case_r1100_geometry.json")
    work = pathlib.Path("F:/velch_tmp/curve38")
    work.mkdir(parents=True, exist_ok=True)

    for cant in (0.107, -0.107):
        raw = json.loads(base.read_text(encoding="utf-8"))
        raw["case_id"] = f"probe_cant_{cant}"
        raw["run"].update({"curve_radius_m": 1100.0, "curve_cant_m": cant,
                           "curve_geometry": True, "align_to_track": True, "x_start_m": 60.0,
                           "duration_s": 0.01, "output_step_s": 0.005})
        raw.setdefault("vehicle", {})["travel_speed_m_s"] = 100.0 / 3.6
        raw.pop("initial_state", None)
        path = work / f"case_{cant}.json"
        path.write_text(json.dumps(raw, indent=1), encoding="utf-8")

        case = load_vehicle_case(path)
        dynamics = vs.VehicleDynamics(case)
        q = np.zeros(dynamics.dimension)
        v = np.zeros(dynamics.dimension)
        placed = vs._place_on_alignment(case, dynamics, q)
        roll = placed[dynamics.topology.require(dynamics.topology.wheelset_id(0), "roll")]
        print(f"\n=== cant {cant:+.3f}: wheelset roll {roll:+.6f} rad")
        _, contacts = dynamics.evaluate(0.0, placed, v)
        for rail in case.rails:
            response = contacts.get(rail.id) if hasattr(contacts, "get") else None
            geometry = getattr(response, "geometry", None)
            pen = 0.0 if geometry is None else geometry.penetration_m
            wz = 0.0 if geometry is None else geometry.wheel_z_m
            rz = 0.0 if geometry is None else geometry.rail_z_m
            fz = (getattr(response, "wheel_force_z_n", 0.0) or 0.0) / 1e3
            print(f"    {str(rail.id):22s} pen {pen * 1e3:+9.3f} mm  rail_z {rz * 1e3:+8.3f}"
                  f"  wheel_z {wz * 1e3:+8.3f}  Fz {fz:+9.3f} kN")
finally:
    subprocess.run(["git", "checkout", "--", "src/velch/vehicle_solver.py"],
                   cwd=str(REPO), check=True)
    print("\nsolver reverted")
