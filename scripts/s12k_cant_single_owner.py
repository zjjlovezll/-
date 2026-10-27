"""Round 39: after fix A, is the level difference 53.5 mm and does the canted curve run?"""

import json
import pathlib
import sys

import numpy as np

REPO = pathlib.Path("F:/ai道岔状态反演辨识/Velch")
sys.path.insert(0, str(REPO / "src"))

import velch.vehicle_solver as vs
from velch.vehicle import load_vehicle_case

BASE = pathlib.Path("F:/velch_tmp/curve_frames/case_r1100_geometry.json")
WORK = pathlib.Path("F:/velch_tmp/curve39")
WORK.mkdir(parents=True, exist_ok=True)


def build(cant: float) -> pathlib.Path:
    raw = json.loads(BASE.read_text(encoding="utf-8"))
    raw["case_id"] = f"cant_{cant:+.3f}".replace(".", "p")
    raw["run"].update({"curve_radius_m": 1100.0, "curve_cant_m": cant,
                       "curve_geometry": True, "align_to_track": True, "x_start_m": 60.0,
                       "duration_s": 0.01, "output_step_s": 0.005})
    raw.setdefault("vehicle", {})["travel_speed_m_s"] = 100.0 / 3.6
    raw.pop("initial_state", None)
    path = WORK / f"case_{cant:+.3f}".replace(".", "p")
    path = path.with_suffix(".json")
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


for cant in (0.107, -0.107):
    case = load_vehicle_case(build(cant))
    dynamics = vs.VehicleDynamics(case)
    q = np.zeros(dynamics.dimension)
    v = np.zeros(dynamics.dimension)
    placed = vs._place_on_alignment(case, dynamics, q)
    roll = placed[dynamics.topology.require(dynamics.topology.wheelset_id(0), "roll")]
    _, contacts = dynamics.evaluate(0.0, placed, v)
    print(f"\n=== cant {cant:+.3f}: roll {roll:+.6f} rad")
    for rail in case.rails:
        response = contacts.get(rail.id) if hasattr(contacts, "get") else None
        geometry = getattr(response, "geometry", None)
        if geometry is None:
            continue
        print(f"    {str(rail.id):18s} rail_z {geometry.rail_z_m * 1e3:+8.3f} mm"
              f"  wheel_z {geometry.wheel_z_m * 1e3:+8.3f}  pen {geometry.penetration_m * 1e3:+8.3f}"
              f"  Fz {(getattr(response, 'wheel_force_z_n', 0.0) or 0.0) / 1e3:+10.3f} kN")

    result = vs.simulate_vehicle(case)
    gates = result.gates
    bad = sorted(name for name, ok in gates.items() if not ok)
    peak = max((abs(float(np.max(np.abs(series)))) for series in [result.forces[:, index]
                for index in range(result.forces.shape[1])]), default=0.0)
    print(f"    status {result.status} gates {sum(gates.values())}/{len(gates)} failing {bad}")
