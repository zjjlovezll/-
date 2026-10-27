"""Name the mode that will not decay.

The zero-irregularity run (`scripts/s9o_long_track.py decay`) holds a 10-17 Hz
component at ~9.1 m/s^2 with only 1.1 % lost over six seconds, on a track with no
irregularity at all.  Something in the model sustains it.  This script answers
*which* something, using the analytic Jacobian we already maintain:

  A = [[0, I], [df/dq, df/dv]]  at the settled state
  eigenvalues of A -> natural frequencies and damping ratios
  eigenvectors     -> which coordinates carry each mode

A mode with damping ratio at or below zero is the suspect: the solver will hold
whatever amplitude the initial condition gave it, forever, and every short-wave
measurement then sits on top of that tone instead of on the track.

Run with PYTHONPATH=src;scripts.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib

import numpy as np

import s9o_long_track as long_track


def settled_state(case_path: pathlib.Path):
    """Load the case and run the same static vertical equilibrium the solver runs."""
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics, _static_vertical_equilibrium, _settle_modal_coordinates

    case = load_vehicle_case(case_path)
    dynamics = VehicleDynamics(case)
    q = np.array(case.initial_q, dtype=float)
    v = np.zeros_like(q)
    if case.equilibrate_vertical:
        for _round in range(2):
            q = _settle_modal_coordinates(dynamics, q, v)
            q, residual = _static_vertical_equilibrium(case, dynamics, q, v)
    return case, dynamics, q, v


def labels(dynamics) -> list[str]:
    names = []
    for body in dynamics.topology.bodies:
        for axis in body.dof:
            names.append(f"{body.id}.{axis}")
    names += [f"rail{i}.{axis}" for i in range(len(dynamics.track.mass)) for axis in ("y", "z")][: len(dynamics.track.mass)]
    names += [f"mode{i + 1}" for i in range(len(dynamics.mass) - len(names))]
    return names


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default=str(long_track.WORK / "case_zero_6s.json"))
    parser.add_argument("--low-hz", type=float, default=8.0)
    parser.add_argument("--high-hz", type=float, default=20.0)
    parser.add_argument("--top", type=int, default=6)
    args = parser.parse_args()

    from velch.jacobian import JacobianAssembler

    case, dynamics, q, v = settled_state(pathlib.Path(args.case))
    assembler = JacobianAssembler(dynamics)
    q_block, v_block = assembler.blocks(0.0, q, v)
    dimension = dynamics.dimension
    system = np.zeros((2 * dimension, 2 * dimension))
    system[:dimension, dimension:] = np.eye(dimension)
    system[dimension:, :dimension] = q_block
    system[dimension:, dimension:] = v_block

    values = np.linalg.eigvals(system)
    upper = values[values.imag > 0.0]
    names = labels(dynamics)
    print(f"dimension {dimension}, {len(upper)} oscillatory modes")
    print(f"{'f Hz':>9} {'zeta':>8} {'|eig|':>9}")

    rows = []
    for value in upper:
        frequency = abs(value) / (2.0 * math.pi)
        zeta = -value.real / abs(value)
        if args.low_hz <= frequency <= args.high_hz:
            rows.append((frequency, zeta, value))
    for frequency, zeta, _ in sorted(rows):
        print(f"{frequency:9.3f} {zeta:8.4f} {abs(_):9.4f}")
    if not rows:
        print("  (nothing in that window)", flush=True)
        return 0

    # participation of the mode closest to the measured tone
    target = sorted(rows, key=lambda item: abs(item[0] - 13.3))[0]
    index = int(np.argmin(np.abs(upper - target[2])))
    vector = np.linalg.eig(system)[1][:, index]
    amplitude = np.abs(vector[:dimension])
    order = np.argsort(amplitude)[::-1][: args.top]
    print()
    print(f"mode at {target[0]:.3f} Hz, zeta {target[1]:+.4f} -- strongest coordinates")
    for position in order:
        name = names[position] if position < len(names) else f"index{position}"
        print(f"  {name:<28} |u| = {amplitude[position]:.3e}")

    payload = {
        "modes": [{"frequency_hz": float(f), "zeta": float(z), "real": float(e.real), "imag": float(e.imag)}
                  for f, z, e in sorted(rows)],
        "target": {"frequency_hz": float(target[0]), "zeta": float(target[1]),
                   "coordinates": [{"name": names[p] if p < len(names) else f"index{p}",
                                    "amplitude": float(amplitude[p])} for p in order]},
    }
    out = pathlib.Path(long_track.WORK) / "modal_audit.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
