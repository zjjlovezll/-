"""Decompose the vertical preload residual of the CRH380A_M case.

Prints the generalised force on every solved DOF at the case's initial state,
the per-contact normal force, and the residual after an unconstrained solve so
the offending equation can be identified without guessing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.optimize import root

VEH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(VEH / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics  # noqa: E402

LABELS = ["wh0 z", "wh1 z", "wh2 z", "wh3 z", "bogie F z", "bogie R z", "carbody z"]


def report(tag: str, force: np.ndarray, indices: list[int]) -> None:
    print(f"  {tag}")
    for label, idx in zip(LABELS, indices):
        print(f"    {label:12s} idx {idx:3d}  F = {force[idx]:14.3f} N")


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else VEH / "validation/crh380a_m/case_A_plain.json"
    case = load_vehicle_case(path)
    dyn = VehicleDynamics(case)
    cfg = case.vehicle
    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    indices = [5 * i + 1 for i in range(4)] + [21, 26, 31]

    print(f"case {case.case_id}  track_kind {case.track_kind}  dof {dyn.dimension}")
    wt = (cfg.carbody.mass_kg + 2 * cfg.bogie.mass_kg + 4 * cfg.wheelset.mass_kg) * cfg.gravity_m_s2
    print(f"total weight {wt:.1f} N   carbody {cfg.carbody.mass_kg * cfg.gravity_m_s2:.1f} N")
    print(f"equilibrate_vertical {case.equilibrate_vertical}")
    print()

    force, _ = dyn.evaluate(0.0, q, v)
    report("at q = initial (no contact expected)", force, indices)

    print()
    print("  per-rail contact at q = initial")
    for rail in case.rails:
        x = case.run.x_start_m + cfg.axle_offsets_m[rail.axle_index]
        sample = rail.profiles.sample(x, 1)
        print(f"    rail {rail.id:22s} axle {rail.axle_index} x {x:8.3f} active={sample is not None}")

    print()
    tol = 0.1 / 1e5

    def residual(values):
        trial = q.copy()
        trial[indices] = values
        f, _ = dyn.evaluate(0.0, trial, v)
        return f[indices] / 1e5

    solved = root(residual, q[indices], method="hybr", options={"xtol": 1e-10})
    print(f"  hybr -> {solved.message}  nfev={solved.nfev}")
    report("residual at hybr solution", residual(solved.x) * 1e5, list(range(7)))
    trial = q.copy()
    trial[indices] = solved.x
    force2, _ = dyn.evaluate(0.0, trial, v)
    report("full generalised force at hybr solution", force2, indices)
    print()
    print(f"  q values: {np.round(solved.x, 6).tolist()}")
    print(f"  wheel z  : {np.round(solved.x[:4] * 1e3, 4).tolist()} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
