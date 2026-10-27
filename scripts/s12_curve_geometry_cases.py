"""With the envelope fix in, can a case that moves the track actually run?

The envelope refusal (``wheel roll made the lower envelope non-monotonic``) was what stopped every
`curve_geometry = true` run, i.e. the only configuration that is geometrically consistent: track on
``y(s) = s^2/(2R)`` *and* vehicle placed on the same line.  Now that the rolled wheel is
single-valued, this asks the two physically consistent cases:

  R = 1100 m, cant 107 mm, 100 km/h  -> balance cant, so every wheel should carry the same load
  R = 1100 m,  cant 150 mm,  66.7 km/h -> balance cant at the largest cant real track can build
"""

import json
import math
import pathlib
import sys

sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\src")

from velch import data_root
from velch.topology import topology_for
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import _load_per_wheel, simulate_vehicle

BASE = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))


def design_speed(cant: float, radius: float) -> float:
    return math.sqrt(cant * 9.81 * radius / 1.5)


CASES = (
    ("R1100_h107_geom", 1100.0, 0.107, 100.0),
    ("R1100_h107_geom_deficient", 1100.0, 0.107, 160.0),
    ("R350_h150_geom", 1100.0, 0.150, design_speed(0.150, 1100.0) * 3.6),
)

for label, radius, cant, speed_kmh in CASES:
    doc = json.loads(json.dumps(BASE))
    doc["run"].update({"x_start_m": 60.0, "duration_s": 0.01, "output_step_s": 0.01,
                       "curve_radius_m": radius, "curve_cant_m": cant,
                       "curve_geometry": True})
    doc["vehicle"]["travel_speed_m_s"] = speed_kmh / 3.6
    doc.pop("initial_state", None)
    path = pathlib.Path(rf"F:\velch_tmp\geom_{label}.json")
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    try:
        case = load_vehicle_case(path)
        result = simulate_vehicle(case)
        topology = topology_for(case)
        even = sum(body.mass_kg for body in topology.bodies) * case.vehicle.gravity_m_s2 / 8.0
        loads = [result.contacts[-1][rail.id].normal_force_n for rail in case.rails]
        per_wheel = _load_per_wheel(case.rails, loads)
        ratios = sorted(value / even for value in per_wheel.values())
        failed = [name for name, ok in result.summary["gates"].items() if not ok]
        verdict = "PASS" if len(per_wheel) == 8 and 0.5 <= ratios[0] and ratios[-1] <= 1.6 else "OUT"
        print(f"{label:26s} v={speed_kmh:5.1f}  {result.summary['result_status']:20s}"
              f" wheels {len(per_wheel)}  ratio {ratios[0]:.3f}..{ratios[-1]:.3f}"
              f"  gates_false {failed}  {verdict}")
    except Exception as exc:
        print(f"{label:26s} v={speed_kmh:5.1f}  FAILED {type(exc).__name__}: {str(exc)[:120]}")
