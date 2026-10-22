"""Per-body contact geometry along the frog for one recorded state.

Reads a finished run's history.csv, rebuilds the 35 vehicle states and reports,
for one axle/side, the contact each rail body finds. Used to explain why the
wheel loses support after the wing rail and how deep it lands on the point rail.

Usage:
    python probe_bodies.py <case.json> <output_dir> [axle] [side]
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from velch.contact import find_graph_contact
from velch.vehicle import load_vehicle_case as load_case

BASE = Path(__file__).resolve().parent

STATE_ORDER = (
    [(f"axle{k + 1}", ("y_m", "z_m", "roll_rad", "spin_rad", "yaw_rad")) for k in range(4)]
    + [(f"bogie{k + 1}", ("y_m", "z_m", "roll_rad", "pitch_rad", "yaw_rad")) for k in range(2)]
    + [("carbody", ("y_m", "z_m", "roll_rad", "pitch_rad", "yaw_rad"))]
)

X_LO, X_HI = 79.2, 83.2


def state_vector(row: dict) -> list[float]:
    out: list[float] = []
    for prefix, fields in STATE_ORDER:
        out.extend(float(row[f"{prefix}_{field}"]) for field in fields)
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    case = load_case(Path(argv[1]))
    out_dir = Path(argv[2])
    axle = int(argv[3]) if len(argv) > 3 else 1
    side = argv[4] if len(argv) > 4 else "right"
    rail = next(r for r in case.rails if r.id == f"axle{axle}_{side}")
    wheel = next(w for w in case.wheels if w.id == rail.wheel_id)
    wh = 5 * rail.axle_index
    rows = list(csv.DictReader((out_dir / "history.csv").open(encoding="utf-8")))
    print(f"rail {rail.id}: bodies {[b.id for b in rail.contact_bodies]}")
    header = f"{'x_m':>8} {'wheel_z_mm':>11} " + " ".join(f"{b.id:>20}" for b in rail.contact_bodies)
    print(header)
    direction = 1 if case.vehicle.travel_speed_m_s >= 0 else -1
    for row in rows:
        x = float(row[f"axle{axle}_x_m"])
        if not (X_LO <= x <= X_HI):
            continue
        q = state_vector(row)
        cells = []
        for body in rail.contact_bodies:
            if not body.active_at(x):
                cells.append(f"{'outside':>20}")
                continue
            sample = body.series.sample(x, direction)
            geometry = find_graph_contact(
                wheel.profile, sample, wheel_y_m=q[wh],
                wheel_z_m=case.vehicle.wheel_center_height_m + q[wh + 1],
                wheel_roll_rad=q[wh + 2], wheel_lateral_offset_m=wheel.lateral_offset_m,
                rail_y_m=0.0, rail_z_m=0.0,
            )
            if geometry is None or geometry.penetration_m <= 0:
                cells.append(f"{'no contact':>20}")
            else:
                cells.append(f"{geometry.y_m * 1e3:6.2f} pen{geometry.penetration_m * 1e3:7.3f}")
        print(f"{x:8.3f} {(case.vehicle.wheel_center_height_m + q[wh + 1]) * 1e3:11.3f} " + " ".join(cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

