"""A1: establish the finite-difference Jacobian reference and its own noise floor.

Before any analytic Jacobian exists there has to be a reference to compare it
against, and that reference has to be shown trustworthy first. This script does
only that: it differentiates the *same* right-hand side the solvers use
(`derivative_pure`) by forward and central differences over a range of steps, at
several states taken from an already converged run, and reports

1. how far central differences move when the step shrinks (self-convergence),
2. how far forward differences sit from central ones,
3. which entries are *not smooth* - they change materially when the state moves
   by 1e-9, which is the signature of a contact switching plane rather than a
   derivative,
4. the scale spread across the Jacobian, which is what sets the achievable
   tolerance: a contact tangent near 1.4e9 N/m next to a suspension link near
   1e5 N/m cannot both be resolved by one global relative step.

Usage:
    python check_jacobian.py                     # states from the frozen baseline run
    python check_jacobian.py --times 0 0.3 0.6 1.2
    python check_jacobian.py --history out_full12_cap05/history.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics  # noqa: E402

CASE = BASE / "case_full12_cap05.json"
HISTORY = BASE / "out_full12_cap05" / "history.csv"
STEPS = (1.0e-4, 1.0e-5, 1.0e-6, 1.0e-7, 1.0e-8)


def _labels(dynamics: VehicleDynamics) -> list[str]:
    """Coordinate labels in the order `VehicleDynamics` packs them."""
    names: list[str] = []
    axes5 = ("y", "z", "roll", "spin", "yaw")
    for axle in range(4):
        names += [f"axle{axle + 1}.{axis}" for axis in axes5]
    for bogie in range(2):
        names += [f"bogie{bogie + 1}.{axis}" for axis in ("y", "z", "roll", "pitch", "yaw")]
    names += [f"carbody.{axis}" for axis in ("y", "z", "roll", "pitch", "yaw")]
    for rail in dynamics.case.rails:
        names += [f"{rail.id}.y", f"{rail.id}.z"]
    dof = len(names)
    return names + [f"d({name})" for name in names]


def _state_from_history(path: Path, time_s: float, case) -> tuple[np.ndarray, float]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    row = min(rows, key=lambda item: abs(float(item["time_s"]) - time_s))
    q: list[float] = []
    axes5 = ("y", "z", "roll", "spin", "yaw")
    for axle in range(4):
        q += [float(row[f"axle{axle + 1}_{axis}_m" if axis in ("y", "z")
                      else f"axle{axle + 1}_{axis}_rad"]) for axis in axes5]
    for bogie in range(2):
        q += [float(row[f"bogie{bogie + 1}_{axis}_m" if axis in ("y", "z")
                      else f"bogie{bogie + 1}_{axis}_rad"]) for axis in ("y", "z", "roll", "pitch", "yaw")]
    q += [float(row[f"carbody_{axis}_m" if axis in ("y", "z")
                  else f"carbody_{axis}_rad"]) for axis in ("y", "z", "roll", "pitch", "yaw")]
    for rail in case.rails:
        q += [float(row[f"{rail.id}_y_m"]), float(row[f"{rail.id}_z_m"])]
    v: list[float] = []
    for axle in range(4):
        for axis in axes5:
            key = (f"axle{axle + 1}_{axis}_m_per_s" if axis in ("y", "z")
                   else f"axle{axle + 1}_{axis}_rad_per_s")
            v.append(float(row[key]))
    for bogie in range(2):
        for axis in ("y", "z", "roll", "pitch", "yaw"):
            key = (f"bogie{bogie + 1}_{axis}_m_per_s" if axis in ("y", "z")
                   else f"bogie{bogie + 1}_{axis}_rad_per_s")
            v.append(float(row[key]))
    for axis in ("y", "z", "roll", "pitch", "yaw"):
        key = (f"carbody_{axis}_m_per_s" if axis in ("y", "z")
               else f"carbody_{axis}_rad_per_s")
        v.append(float(row[key]))
    for rail in case.rails:
        v += [float(row[f"{rail.id}_y_m_per_s"]), float(row[f"{rail.id}_z_m_per_s"])]
    return np.array(q + v, dtype=float), float(row["time_s"])


def jacobian(dynamics: VehicleDynamics, t_s: float, state: np.ndarray,
             step: float, central: bool) -> np.ndarray:
    size = state.size
    scale = np.maximum(1.0, np.abs(state))
    result = np.empty((size, size))
    base = dynamics.derivative_pure(t_s, state)
    for index in range(size):
        delta = step * scale[index]
        plus = state.copy()
        plus[index] += delta
        forward = dynamics.derivative_pure(t_s, plus)
        if central:
            minus = state.copy()
            minus[index] -= delta
            result[:, index] = (forward - dynamics.derivative_pure(t_s, minus)) / (2.0 * delta)
        else:
            result[:, index] = (forward - base) / delta
    return result


def report_state(name: str, dynamics: VehicleDynamics, t_s: float, state: np.ndarray,
                 labels: list[str]) -> dict[str, object]:
    print(f"\n--- {name}: t={t_s:.6f} s, |y|max={np.max(np.abs(state)):.4g} ---")
    forward = {step: jacobian(dynamics, t_s, state, step, central=False) for step in STEPS}
    central = {step: jacobian(dynamics, t_s, state, step, central=True) for step in STEPS}
    reference = central[1.0e-6]
    scale = float(np.max(np.abs(reference)))

    print(f"{'step':>9}{'central drift':>15}{'forward - central':>20}")
    for step in STEPS:
        drift = float(np.max(np.abs(central[step] - reference))) / scale
        differ = float(np.max(np.abs(forward[step] - central[step]))) / scale
        print(f"{step:>9.0e}{drift:>15.2e}{differ:>20.2e}")

    # Non-smooth entries: a 1e-9 m move must not change a derivative by >1 %.
    moved = state.copy()
    moved[1] += 1.0e-9
    nudged = jacobian(dynamics, t_s, moved, 1.0e-6, central=True)
    changed = np.abs(nudged - reference) > 0.01 * np.maximum(1.0, np.abs(reference))
    rows, cols = np.nonzero(changed)
    print(f"entries moved >1% by a 1e-9 m state nudge: {len(rows)}")
    for row, col in list(zip(rows, cols))[:8]:
        print(f"    d({labels[row]}) / d({labels[col]})"
              f"  {reference[row, col]:+.3e} -> {nudged[row, col]:+.3e}")

    nonzero = np.abs(reference[reference != 0.0])
    print(f"scale: max |J| {scale:.3e}, min |J|>0 {float(nonzero.min()):.3e}, "
          f"spread {scale / float(nonzero.min()):.1e}x, nonzeros {int(nonzero.size)}")
    return {"scale": scale, "changed": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default=str(CASE))
    parser.add_argument("--history", default=str(HISTORY))
    parser.add_argument("--times", type=float, nargs="+", default=[0.0, 0.3, 0.6065, 1.2])
    args = parser.parse_args()

    case = load_vehicle_case(args.case)
    dynamics = VehicleDynamics(case)
    try:
        labels = _labels(dynamics)
        for time_s in args.times:
            state, actual = _state_from_history(Path(args.history), time_s, case)
            report_state(f"history t={time_s:g}", dynamics, actual, state, labels)
    finally:
        dynamics.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
