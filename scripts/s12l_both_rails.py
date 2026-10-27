"""Round 40: both rails and all four wheel centres on one placed state."""

import json
import pathlib
import sys

import numpy as np

REPO = pathlib.Path("F:/ai道岔状态反演辨识/Velch")
sys.path.insert(0, str(REPO / "src"))

import velch.vehicle_solver as vs
from velch.vehicle import load_vehicle_case

BASE = pathlib.Path("F:/velch_tmp/curve_frames/case_r1100_geometry.json")
WORK = pathlib.Path("F:/velch_tmp/curve40")
WORK.mkdir(parents=True, exist_ok=True)


def build(cant: float) -> pathlib.Path:
    raw = json.loads(BASE.read_text(encoding="utf-8"))
    raw["case_id"] = f"probe_{cant:+.3f}"
    raw["run"].update({"curve_radius_m": 1100.0, "curve_cant_m": cant,
                       "curve_geometry": True, "align_to_track": True, "x_start_m": 60.0,
                       "duration_s": 0.01, "output_step_s": 0.005})
    raw.setdefault("vehicle", {})["travel_speed_m_s"] = 100.0 / 3.6
    raw.pop("initial_state", None)
    path = WORK / f"case_{cant:+.3f}.json".replace(".", "p").replace("+", "p")
    path = path.with_suffix(".json")
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


for cant in (0.107,):
    case = load_vehicle_case(build(cant))
    dynamics = vs.VehicleDynamics(case)
    q = np.zeros(dynamics.dimension)
    v = np.zeros(dynamics.dimension)
    placed = vs._place_on_alignment(case, dynamics, q)
    gauge = 2.0 * abs(float(case.wheels[0].lateral_offset_m))
    theta = np.arcsin(cant / gauge)
    print(f"\n=== cant {cant:+.3f}: theta {theta:+.6f} rad, b sin(theta) "
          f"{0.5 * gauge * np.sin(theta) * 1e3:+.3f} mm, curve_geometry "
          f"{getattr(case.run, 'curve_geometry', None)}")

    for axle in range(4):
        wid = dynamics.topology.wheelset_id(axle)
        z = placed[dynamics.topology.require(wid, "z")]
        roll = placed[dynamics.topology.require(wid, "roll")]
        y = placed[dynamics.topology.require(wid, "y")]
        x = float(case.run.x_start_m) + float(case.vehicle.axle_offsets_m[axle])
        print(f"  wheel {axle}: x {x:7.2f}  y {y * 1e3:+9.3f} mm  z {z * 1e3:+9.3f} mm"
              f"  roll {roll:+.6f}")

    print("  rails (sampled at the axle mileages):")
    for rail in case.rails:
        bodies = getattr(rail, "contact_bodies", None) or getattr(rail, "bodies", None)
        if not bodies:
            print(f"    {str(rail.id):18s} no bodies")
            continue
        series = bodies[0].series
        columns = []
        for axle in range(4):
            x = float(case.run.x_start_m) + float(case.vehicle.axle_offsets_m[axle])
            sample = series.sample(x, 1)
            columns.append((float(np.max(sample.profile.z_m)), float(np.mean(sample.profile.y_m))))
        print(f"    {str(rail.id):18s} max z {[round(c[0] * 1e3, 3) for c in columns]} mm"
              f"  mean y {[round(c[1] * 1e3, 2) for c in columns]} mm")
