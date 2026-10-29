"""Seat the crown-corrected switch case, and find out what the unknown set has to contain.

Two measured facts force this probe.  The rail crowns sit 1.52059 m apart while the wheelset's planes are
1.49300 m apart (13.8 mm outboard per side), so the wheel rides the gauge corner; correcting the crown
separation to 1.49366 keeps the design lowering at 0.000 mm but the vertical-only seat then stops
converging with `gtol`.  That combination says the old convergence was resting on the steep corner, and the
question is which extra coordinate makes the tread support determinate.

Roll is the candidate: it moves load between the two sides of one wheelset without asking the creep law for
a lateral force at zero speed (which is why y and yaw are rank-deficient -- measured cond 3.76e12 in round
30).  The probe therefore solves {all body z, elastic rail z, every wheelset roll} and reports, per wheel,
the load ratio and whether `lever_y` stays inside the rail head (B045).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

import velch.vehicle_solver as solver
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _load_per_wheel, _seat

EVEN_SHARE_N = 59_662.0


def _case(path: Path, *, x_start: float, seat_at: float) -> Path:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["run"].update({"x_start_m": x_start, "seat_x_start_m": seat_at, "duration_s": 0.001,
                       "output_step_s": 0.001, "max_solver_step_s": 5e-5,
                       "align_to_track": True})
    raw["vehicle"]["travel_speed_m_s"] = 80.0 / 3.6
    raw.pop("initial_state", None)
    out = Path("../scratch/s61/case.json").resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(raw), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="../scratch/s60/case_crown1493.json")
    parser.add_argument("--x-start", type=float, default=55.0)
    parser.add_argument("--seat-at", type=float, default=45.0)
    parser.add_argument("--with-roll", action="store_true")
    args = parser.parse_args()

    case = load_vehicle_case(_case(Path(args.case).resolve(), x_start=args.x_start, seat_at=args.seat_at))
    solver._placement_enabled = lambda run: True          # probe only; lets the alignment run
    dynamics = VehicleDynamics(case)
    topology = dynamics.topology
    n = dynamics.dimension
    zero = np.zeros(n)
    try:
        q, residual = _seat(case, dynamics, zero, zero)
        print(f"coordinates {n}   shipped seat residual {residual:.3e} N")
    except Exception as exc:                      # the shipped seat is what this probe is asking about
        q, residual = np.array(zero), float("nan")
        _ = exc
        print(f"coordinates {n}   shipped seat FAILED: {type(exc).__name__}: {exc}")

    rows = [topology.require(body.id, "z") for body in topology.bodies if "z" in body.dof]
    if case.track_kind == "local_compliant":
        rows += [topology.body_dimension + 2 * i + 1 for i in range(len(case.rails))]
    if args.with_roll:
        rows += [topology.require(body.id, "roll") for body in topology.bodies
                 if body.kind == "wheelset" and "roll" in body.dof]
    rows = sorted(set(rows))
    print(f"unknowns {len(rows)} ({'z + roll' if args.with_roll else 'z only'})")

    base = np.array(solver._align_to_track_frame(case, dynamics, np.array(zero, dtype=float)))
    latency, tilt = solver._gauge_centre(case, args.x_start, dynamics, 80.0 / 3.6)
    print(f"aligned base: centre {latency:+.6f} m, tangent {tilt:+.6f}")

    def scatter(values: np.ndarray) -> np.ndarray:
        state = np.array(base, dtype=float, copy=True)
        state[rows] = values
        return state

    def evaluate(values: np.ndarray) -> np.ndarray:
        try:
            force, _ = dynamics.evaluate(0.0, scatter(values), np.zeros(n))
        except solver.SimulationFailure:
            # A trial that puts a wheel on a flank has no residual, only a barrier: the guard is
            # never relaxed, the step is simply counted as infeasible.
            return np.full(len(rows), solver._SEAT_BARRIER_RESIDUAL)
        return np.asarray(force, dtype=float)[rows] / 1e5

    best = None
    for dz in (0.0, -2e-4, -6.5e-5):
        start = np.array(q, dtype=float, copy=True)
        for index in rows[:len(topology.bodies)] if not args.with_roll else rows:
            start[index] += dz if index in rows[:20] else 0.0
        solution = least_squares(evaluate, start[rows], method="trf",
                                 xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=600)
        state = scatter(solution.x)
        norm = float(np.max(np.abs(evaluate(solution.x))))
        if best is None or norm < best[0]:
            best = (norm, state, dz)
        print(f"  seed dz {dz*1e6:+7.1f} um -> |r|max {norm:8.3e}  ({solution.status})")

    norm, state, dz = best
    dynamics.evaluate(0.0, state, np.zeros(n))
    loads = _load_per_wheel(case.rails, [dynamics.body_contacts[r.id] for r in case.rails])
    print(f"best |r|max {norm:.3e} N (seed {dz*1e6:+.1f} um)")
    rail_by_id = {r.id: r for r in case.rails}
    for (axle, side), value in sorted(loads.items()):
        print(f"  axle{axle}{side}  {value/1e3:8.2f} kN  {value/EVEN_SHARE_N:5.3f}x")
    inside = []
    for rail in case.rails:
        entry = dynamics.body_contacts.get(rail.id)
        sequence = entry if isinstance(entry, tuple) else ((entry,) if entry else ())
        for response in sequence:
            if response is None or not response.active:
                continue
            geometry = response.geometry
            sample = rail.bodies[0].series.sample(float(geometry.rail_x_m), 1.0).profile
            head = (float(sample.y_m.min()), float(sample.y_m.max()))
            ok = head[0] - 1e-4 <= float(geometry.lever_y_m) <= head[1] + 1e-4
            inside.append(ok)
            print(f"    {rail.id:12s} lever_y {float(geometry.lever_y_m):+8.4f}  head {head[0]:+.4f}..{head[1]:+.4f}"
                  f"  {'inside' if ok else 'OUTSIDE'}")
    print(f"contacts inside the rail head: {sum(inside)}/{len(inside)}")
    return 0 if norm < 1e-3 else 2


if __name__ == "__main__":
    raise SystemExit(main())
