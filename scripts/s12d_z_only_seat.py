"""Does an equilibrium exist near the aligned state on the curved case?

Round 18: the frame probe showed the rails are shifted (+45.455 mm at 70 m), `_gauge_centre` reads
that correctly, and the alignment writes the same offset into the wheelsets -- so geometry is not
the mismatch.  That leaves the seat's own search.  This probe keeps y/yaw/roll at their aligned
values and solves **only the four wheelset z offsets** by a damped Newton step on the per-axle
normal force.  If a near-equal-load state exists, the geometry is sound and the seat's multi-start
least squares is what fails on a non-smooth 24-unknown problem; if it does not exist, the geometry
still needs work.

Run: python -X utf8 scripts/s12d_z_only_seat.py
"""

from __future__ import annotations

import json
import pathlib

import numpy as np

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _align_to_track_frame

WORK = pathlib.Path(r"F:\velch_tmp\s12d")
RADIUS_M = 1100.0
X_START_M = 60.0
SPEED_KMH = 80.0


def build() -> pathlib.Path:
    raw = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
    raw.pop("initial_state", None)
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw["run"].update({"duration_s": 0.004, "output_step_s": 0.004, "x_start_m": X_START_M,
                       "curve_radius_m": RADIUS_M, "curve_cant_m": 0.0, "curve_geometry": True})
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / "case.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


def axle_loads(dynamics: VehicleDynamics) -> dict[str, float]:
    loads: dict[str, float] = {}
    for key, responses in dict(dynamics.body_contacts).items():
        total = 0.0
        for response in responses:
            geometry = getattr(response, "geometry", None)
            if geometry is not None and geometry.penetration_m > 0.0:
                total += float(response.wheel_force_z_n)
        loads[key] = total
    return loads


def main() -> int:
    case = load_vehicle_case(build())
    dynamics = VehicleDynamics(case)
    topology = dynamics.topology
    q = np.asarray(_align_to_track_frame(case, dynamics, [0.0] * dynamics.dimension), dtype=float)
    v = np.zeros(dynamics.dimension)

    share = sum(body.mass_kg for body in topology.bodies) * case.vehicle.gravity_m_s2 / 8.0
    z_rows = {axle: topology.require(f"wheelset{axle}", "z") for axle in (1, 2, 3, 4)}
    stiffness = share / 65.0e-6  # N/m, the frozen static-penetration ratio
    print(f"even share per wheel {share:.1f} N   assumed contact stiffness {stiffness:.3e} N/m")

    for step in range(14):
        dynamics.evaluate(0.0, q, v)
        loads = axle_loads(dynamics)
        per_axle = {axle: loads.get(f"axle{axle}_left", 0.0) + loads.get(f"axle{axle}_right", 0.0)
                    for axle in (1, 2, 3, 4)}
        text = "  ".join(f"{axle}: {per_axle[axle] / 1e3:8.1f} kN" for axle in (1, 2, 3, 4))
        left = "  ".join(f"{loads.get(f'axle{axle}_left', 0.0) / 1e3:6.1f}" for axle in (1, 2, 3, 4))
        right = "  ".join(f"{loads.get(f'axle{axle}_right', 0.0) / 1e3:6.1f}" for axle in (1, 2, 3, 4))
        print(f" {step:2d}  total {text}   left [{left}]  right [{right}]")
        worst = max(abs(per_axle[axle] - 2.0 * share) for axle in per_axle)
        if worst < 0.02 * 2.0 * share:
            print(f"  converged: worst axle error {worst:.1f} N")
            return 0
        for axle, row in z_rows.items():
            error = per_axle[axle] - 2.0 * share
            # lifting the wheelset (increasing z) reduces penetration and therefore the load
            q[row] += float(np.clip(0.5 * error / stiffness, -1.0e-3, 1.0e-3))
    print("  no equilibrium found from the aligned state by z alone")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
