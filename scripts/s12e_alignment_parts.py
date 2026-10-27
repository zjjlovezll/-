"""Which aligned coordinate kills the right rail?

Round 19: at the aligned state on an R = 1100 m geometry-route curve, the very first `evaluate`
carries 150 690 kN on the left rail and **nothing at all** on the right.  The aligned state has three
things the straight case does not: a lateral offset, a yaw, and a rail surface shifted by
`CurveSeries`.  This probe applies them one at a time to the same straight-table case and prints the
per-rail normal force, so the culprit is named instead of guessed.

Run: python -X utf8 scripts/s12e_alignment_parts.py
"""

from __future__ import annotations

import json
import pathlib

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _align_to_track_frame, _gauge_centre

WORK = pathlib.Path(r"F:\velch_tmp\s12e")
RADIUS_M = 1100.0
X_START_M = 60.0
SPEED_KMH = 80.0


def build(*, curved_series: bool) -> pathlib.Path:
    raw = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
    raw.pop("initial_state", None)
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw["run"].update({"duration_s": 0.004, "output_step_s": 0.004, "x_start_m": X_START_M,
                       "curve_radius_m": RADIUS_M, "curve_cant_m": 0.0,
                       "curve_geometry": curved_series})
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / f"case_{'curved' if curved_series else 'straight'}.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


def loads(dynamics: VehicleDynamics) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, responses in dict(dynamics.body_contacts).items():
        total = 0.0
        for response in responses:
            geometry = getattr(response, "geometry", None)
            if geometry is not None and geometry.penetration_m > 0.0:
                total += float(response.wheel_force_z_n)
        out[key] = total
    return out


def show(label: str, dynamics: VehicleDynamics, q) -> None:
    dynamics.evaluate(0.0, q, list(0.0 for _ in q))
    per = loads(dynamics)
    text = "  ".join(f"{key}={value / 1e3:.1f}kN" for key, value in sorted(per.items())
                     if key.startswith("axle1"))
    print(f"  {label:>34}: {text}")


def main() -> int:
    for curved_series in (False, True):
        case = load_vehicle_case(build(curved_series=curved_series))
        dynamics = VehicleDynamics(case)
        aligned = _align_to_track_frame(case, dynamics, [0.0] * dynamics.dimension)
        topology = dynamics.topology
        y_rows = [topology.require(f"wheelset{axle}", "y") for axle in (1, 2, 3, 4)] \
            if all("y" in b.dof for b in topology.wheelsets()) else []
        yaw_rows = [topology.require(f"wheelset{axle}", "yaw") for axle in (1, 2, 3, 4)] \
            if all("yaw" in b.dof for b in topology.wheelsets()) else []
        centre, tangent = _gauge_centre(case, X_START_M + case.vehicle.axle_offsets_m[0])
        print(f"\nseries {'curved' if curved_series else 'straight'}: "
              f"gauge centre at axle1 {centre:+.6f} m, tangent {tangent:+.6e}")

        variants = {
            "aligned (y + yaw)": list(aligned),
            "yaw only (y = 0)": [0.0 if row in y_rows else value
                                 for row, value in enumerate(aligned)],
            "y only (yaw = 0)": [0.0 if row in yaw_rows else value
                                 for row, value in enumerate(aligned)],
            "neither (straight state)": [0.0 if (row in y_rows or row in yaw_rows) else value
                                         for row, value in enumerate(aligned)],
        }
        for label, q in variants.items():
            show(label, dynamics, q)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
