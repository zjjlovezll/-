"""Report the static vertical gate (per-contact normal force and penetration).

The frozen oracle is 59 680.577 N per contact with 65.5 um penetration on the straight
track.  This prints what each candidate case currently yields, so the guard test can
pin the case that belongs to the oracle family instead of guessing.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics, _static_vertical_equilibrium  # noqa: E402

BASE = pathlib.Path(__file__).resolve().parents[1] / "validation" / "crh380a_m"
CANDIDATES = [
    "case_A_plain.json",
    "case_frog_N_strip05.json",
    "case_thru_Z_local_rail_0p05s.json",
]


def main() -> int:
    for name in CANDIDATES:
        path = BASE / name
        if not path.exists():
            print(f"{name:32s} missing")
            continue
        try:
            case = load_vehicle_case(path)
            dynamics = VehicleDynamics(case)
            q = np.array(case.initial_q, dtype=float)
            v = np.array(case.initial_v, dtype=float)
            residual = float("nan")
            if case.equilibrate_vertical:
                q, residual = _static_vertical_equilibrium(case, dynamics, q, v)
            _force, responses = dynamics.evaluate(0.0, q, v)
            forces = [response.normal_force_n for response in responses.values()]
            active = [value for value in forces if value > 0.0]
            print(f"{name:32s} dof={dynamics.dimension:3d} contacts={len(forces):2d} "
                  f"active={len(active):2d} N_min={min(active, default=0.0):10.3f} "
                  f"N_max={max(active, default=0.0):10.3f} "
                  f"vertical1={q[1] * 1e3:+.4f} mm residual={abs(residual):.2e}")
        except Exception as exc:  # noqa: BLE001 - diagnostic script
            print(f"{name:32s} ERROR {type(exc).__name__}: {str(exc)[:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
