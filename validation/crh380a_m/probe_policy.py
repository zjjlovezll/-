"""Print what the solver actually computes at t=0 for a case (policy smoke test)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from velch.vehicle import load_vehicle_case           # noqa: E402
from velch.vehicle_solver import VehicleDynamics    # noqa: E402


def main() -> int:
    path = Path(sys.argv[1])
    case = load_vehicle_case(path)
    contact = case.contact
    print("case:", case.case_id)
    print("policies: normal=%s stiffness=%s geometry=%s damping=%s dstrip=%.4g mm" % (
        contact.normal_policy, contact.stiffness_policy, contact.geometry_policy,
        contact.damping_policy, contact.strip_dy_m * 1e3))
    dynamics = VehicleDynamics(case)
    try:
        force, contacts = dynamics.evaluate(0.0, case.initial_q, case.initial_v)
        for key in ("axle1_right", "axle1_left"):
            response = contacts[key]
            geometry = response.geometry
            if geometry is None:
                print(f"{key}: no contact")
                continue
            print(f"{key}: y={geometry.y_m * 1e3:8.3f} mm  pen={geometry.penetration_m * 1e6:8.2f} um  "
                  f"halfwidth={geometry.half_width_m * 1e3:7.3f} mm  "
                  f"R*={geometry.radius_star_m:7.4f} m  C={geometry.stiffness_n_m_1p5:.4g}  "
                  f"N={response.normal_force_n / 1e3:7.3f} kN")
    finally:
        dynamics.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
