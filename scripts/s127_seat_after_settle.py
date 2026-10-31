"""Which gauge settings survive the seat the integrator actually performs?

Round 270 seated nine gauge variants once each and got 8/8 contacts every time.  Then the first
time history at -4 mm failed inside `_integrate_vehicle`, at the *second* seat -- the one that runs
after the modal coordinates have settled -- with `no seed converged`.  So "it seats" and "it can be
integrated" are different questions, and the difference decides how far the gauge lever reaches.

This probe answers it for all nine settings: first seat, modal settle, second seat.  It is the same
sequence `_integrate_vehicle` uses (round 247), so a pass here is a necessary condition for a run
to start at all.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

from velch.solver import SimulationFailure
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat, _settle_modal_coordinates

ROOT = pathlib.Path(__file__).resolve().parents[1]
VARIANTS = ROOT.parent / "scratch" / "s126"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "seat_after_settle.json"
DELTAS_MM = (-8.0, -6.0, -4.0, -2.0, 0.0, 2.0, 4.0, 6.0, 8.0)
SPEED_KMH = 80.0
LATERAL_TOLERANCE_N = 20.0


def _variant(delta: float) -> pathlib.Path:
    return VARIANTS / f"one_set_gauge{delta:+.0f}mm.json"


def probe(delta: float) -> dict:
    case = load_vehicle_case(_variant(delta))
    dynamics = VehicleDynamics(case)
    q = np.asarray(case.initial_q, dtype=float)
    velocity = np.asarray(case.initial_v, dtype=float)
    for index in (1, 2, 3, 4):
        velocity[dynamics.topology.require(f"wheelset{index}", "spin")] = SPEED_KMH / 3.6 / 0.43
    row: dict = {"delta_mm": delta, "variant": str(_variant(delta).relative_to(ROOT.parent))}

    try:
        q, first = _seat(case, dynamics, q, velocity)
        row["first_seat_n"] = float(first)
    except SimulationFailure as exc:
        row.update(first_seat_n=None, settled=False, second_seat_n=None, note=str(exc))
        return row

    wheel_y = [dynamics.topology.require(f"wheelset{i}", "y") for i in (1, 2, 3, 4)]
    row["y_after_first_mm"] = float(1e3 * np.mean([q[r] for r in wheel_y]))

    settled = _settle_modal_coordinates(dynamics, np.asarray(q, dtype=float), velocity)
    row["y_after_settle_mm"] = float(1e3 * np.mean([settled[r] for r in wheel_y]))

    try:
        q2, second = _seat(case, dynamics, settled, velocity)
        row.update(settled=True, second_seat_n=float(second), y_final_mm=float(1e3 * np.mean([q2[r] for r in wheel_y])))
        row["sustainable"] = bool(second <= 1e-5)
    except SimulationFailure as exc:
        # the lateral floor is what refuses the seed; read it once so the number is not a rumour
        floor = None
        try:
            from velch.vehicle_solver import _static_vertical_equilibrium  # noqa: PLC0415
            _static_vertical_equilibrium(case, dynamics, settled, velocity)
        except SimulationFailure:
            pass
        row.update(settled=False, second_seat_n=None, sustainable=False, note=str(exc), lateral_floor_unknown=True)
    return row


def main() -> int:
    rows = [probe(delta) for delta in DELTAS_MM]
    print(f"{'delta':>7} {'first N':>10} {'y1 mm':>8} {'y2 mm':>8} {'second N':>10}  sustainable")
    for row in rows:
        print(f"{row['delta_mm']:+7.1f} {row.get('first_seat_n') or float('nan'):10.2e} "
              f"{row.get('y_after_first_mm', float('nan')):8.3f} {row.get('y_after_settle_mm', float('nan')):8.3f} "
              f"{row.get('second_seat_n') or float('nan'):10.2e}  {row.get('sustainable')}")
    good = [row["delta_mm"] for row in rows if row.get("sustainable")]
    print(f"\nsustainable gauge settings: {good}")
    print(f"the integrator's first seat needs a sustainable setting, so the usable lever is "
          f"{min(good) if good else float('nan'):+.1f} .. {max(good) if good else float('nan'):+.1f} mm")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"speed_kmh": SPEED_KMH, "rows": rows, "sustainable_mm": good,
                                  "report": "seat_after_settle"}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"data -> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
