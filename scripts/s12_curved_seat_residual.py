"""Print the residuals of a curved seat that never converges.

Round 17 of the goal: the R = 1100 m curve (and the 18 号道岔 diverging route) stop in
`_static_vertical_equilibrium` with `xtol termination condition is satisfied`, and the placed state
carries a wheel vertical force of 1.46e8 N.  This probe records every `evaluate` call the seat makes
and dumps the last one: which rows carry the residual, how many patches are active, and what the
per-patch normal forces and penetrations are.

Run: python -X utf8 scripts/s12_curved_seat_residual.py
"""

from __future__ import annotations

import json
import pathlib
import traceback

import numpy as np

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics
from velch.vehicle_solver import _static_vertical_equilibrium
from velch.vehicle_solver import _align_to_track_frame

WORK = pathlib.Path(r"F:\velch_tmp\seat12")
RADIUS_M = 1100.0
X_START_M = 60.0
SPEED_KMH = 80.0

# (label, run overrides)
VARIANTS = (
    ("curve-geometry-cant0", {"curve_radius_m": RADIUS_M, "curve_cant_m": 0.0, "curve_geometry": True}),
    ("curve-geometry-1mm", {"curve_radius_m": RADIUS_M, "curve_cant_m": 0.0, "curve_geometry": True,
                            "duration_s": 0.01}),
)


def build(overrides: dict) -> pathlib.Path:
    raw = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
    raw.pop("initial_state", None)
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw["run"].update({"duration_s": 0.01, "output_step_s": 0.01, "x_start_m": X_START_M})
    raw["run"].update(overrides)
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / f"{overrides and list(overrides.values())[0]!s}.json"
    path = WORK / "case.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


def main() -> int:
    path = build(VARIANTS[0][1])
    case = load_vehicle_case(path)
    dynamics = VehicleDynamics(case)

    calls: list[tuple[np.ndarray, np.ndarray]] = []
    original = dynamics.evaluate

    def recording(t_s: float, q: np.ndarray, v: np.ndarray):
        # evaluate returns (force, diagnostics) -- wrapping the tuple was my own bug.
        force, extra = original(t_s, q, v)
        calls.append((np.array(q, dtype=float), np.array(force, dtype=float)))
        return force, extra

    dynamics.evaluate = recording  # type: ignore[assignment]

    print(f"case {path.name}: R = {RADIUS_M:g} m, cant 0, {SPEED_KMH:g} km/h, x_start {X_START_M:g} m")
    curved = bool(getattr(case.run, "curve_radius_m", None)) or bool(getattr(case.run, "curve_geometry", False))
    print(f"  dimension {dynamics.dimension}  curved {curved}  "
          f"curvature {dynamics._curvature_1_per_m:.6e} 1/m")
    q0 = np.zeros(dynamics.dimension, dtype=float)
    v0 = np.zeros(dynamics.dimension, dtype=float)
    for body_id, value in (("wheelset1", -1.0e-3), ("wheelset2", -1.0e-3),
                           ("wheelset3", -1.0e-3), ("wheelset4", -1.0e-3)):
        try:
            q0[dynamics.topology.require(body_id, "z")] = value
        except Exception:  # noqa: BLE001
            pass
    try:
        # The real path seats an *aligned* state: without this the probe would measure a vehicle
        # standing 45 mm beside its rails and blame the seat for the mismatch (it did).
        q0 = _align_to_track_frame(case, dynamics, q0)
        print(f"  aligned: wheelset1.y {q0[dynamics.topology.require('wheelset1', 'y')] * 1e3:+.3f} mm, "
              f"yaw {q0[dynamics.topology.require('wheelset1', 'yaw')]:+.6f} rad")
        seated, error = _static_vertical_equilibrium(case, dynamics, q0, v0)
        print(f"  the seat CONVERGED, residual {error:.3e}")
        q0 = seated
    except Exception as error:  # noqa: BLE001
        print(f"  the seat failed: {type(error).__name__}: {str(error)[:120]}")
        traceback.print_exc()
    print(f"  evaluate calls {len(calls)}  barrier hits {dynamics.seat_barrier_hits}")

    if not calls:
        return 1
    q, force = calls[-1]
    names = []
    for body in dynamics.topology.bodies:
        for axis in body.dof:
            names.append(f"{body.id}.{axis}")
    share = sum(body.mass_kg for body in dynamics.topology.bodies) * 9.81 / 8.0
    print(f"  even share {share:.1f} N")
    order = np.argsort(-np.abs(force))[:10]
    print("  largest force rows:")
    for index in order:
        print(f"    {names[index]:>28}  {force[index]:+15.4e} N  ({force[index] / 1e5:+.3e} scaled)")

    contacts = dynamics.body_contacts
    print(f"  contacts: {len(contacts)} bodies")
    active, deepest = 0, 0.0
    for key, responses in dict(contacts).items():
        for response in responses:
            geometry = getattr(response, "geometry", None)
            if geometry is None:
                continue
            pen = float(geometry.penetration_m)
            deepest = max(deepest, pen)
            if pen > 0.0:
                active += 1
                print(f"    {key:>22}  N = {response.wheel_force_z_n:+12.1f} N  "
                      f"penetration {pen * 1e6:+9.2f} um")
    print(f"  active patches {active}  deepest penetration {deepest * 1e6:.2f} um")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
