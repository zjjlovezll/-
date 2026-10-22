"""Which position columns does the analytic Jacobian get wrong, and by how much?

Prints, per state column, the finite-difference column magnitude and the relative
error of the analytic column.  The pattern identifies which chain-rule term is
missing:  lever-arm (`dJ/dq`), contact-law, or track coupling.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from velch.jacobian import JacobianAssembler  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import (  # noqa: E402
    VehicleDynamics,
    _static_vertical_equilibrium,
)

AXES = ("y", "z", "roll", "spin", "yaw")
BOGIE_AXES = ("y", "z", "roll", "pitch", "yaw")


def labels(case) -> list[str]:
    out: list[str] = []
    for axle in range(4):
        out += [f"axle{axle + 1}_{axis}" for axis in AXES]
    for bogie in range(2):
        out += [f"bogie{bogie + 1}_{axis}" for axis in BOGIE_AXES]
    out += [f"carbody_{axis}" for axis in BOGIE_AXES]
    for rail in case.rails:
        out += [f"{rail.id}_y", f"{rail.id}_z"]
    return out


def main() -> int:
    case = load_vehicle_case(HERE / "case_full12_cap05.json")
    dynamics = VehicleDynamics(case)
    try:
        n = dynamics.dimension
        q = np.array(case.initial_q, dtype=float)
        v = np.array(case.initial_v, dtype=float)
        q, _ = _static_vertical_equilibrium(case, dynamics, q, v)
        assembler = JacobianAssembler(dynamics)
        analytic_q, _ = assembler.blocks(0.0, q, v)
        step = 1.0e-7
        scale = np.maximum(1.0, np.abs(np.concatenate((q, v))))
        finite = np.empty((n, n))
        for index in range(n):
            delta = step * scale[index]
            plus = np.concatenate((q, v)).copy()
            minus = plus.copy()
            plus[index] += delta
            minus[index] -= delta
            finite[:, index] = (dynamics.derivative_pure(0.0, plus)[n:]
                                - dynamics.derivative_pure(0.0, minus)[n:]) / (2.0 * delta)
        names = labels(case)
        magnitude = np.max(np.abs(finite), axis=0)
        error = np.max(np.abs(analytic_q - finite), axis=0) / np.maximum(
            magnitude, 1.0e-300)
        print(f"n={n}  max|Jq_fd|={magnitude.max():.3e}")
        print(f"{'col':>4}{'dof':>18}{'|col| fd':>12}{'rel err':>10}{'flag':>7}")
        order = np.argsort(-error)
        for index in order:
            flag = "BAD" if error[index] > 1.0e-3 else "ok"
            print(f"{index:>4}{names[index]:>18}{magnitude[index]:>12.2e}"
                  f"{error[index]:>10.2e}{flag:>7}")
    finally:
        dynamics.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
