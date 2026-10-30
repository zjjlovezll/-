"""Test the pre-registered two-dimensional blade-onset criterion with the wheelset's lateral state.

Round 219 withdrew the mileage-only pass: the blade picked up load at 68.152 m when the run entered the
lowering ramp from 52 m, and never touched when it entered from 62 or 66.5 m.  The reason on record is
that the wheel surface height at the blade's lateral position is set by the wheelset's lateral
displacement, so the criterion has to carry `q[y]`.

This prints, for each entry point, the first blade load, the axle mileage there, and the wheelset's
lateral displacement and yaw at the same frame -- the two quantities the null test needs.

    PYTHONPATH=src python -X utf8 scripts/s56_blade_onset_2d.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
CASE = HERE.parent / "scratch" / "s52" / "case_two_body_switch.json"
TIP_M = 60.95
ONSET_FROM_TIP_M = 7.208
ONSET_AT_M = TIP_M + ONSET_FROM_TIP_M


def one(*, x_start: float, speed_kmh: float, duration_s: float) -> dict[str, object]:
    from velch import vehicle_solver as solver_module
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics, simulate_vehicle

    raw = json.loads(CASE.read_text(encoding="utf-8"))
    raw["run"].update(
        {
            "x_start_m": x_start,
            "seat_x_start_m": 45.0,
            "duration_s": duration_s,
            "output_step_s": min(5.0e-4, duration_s / 40.0),
            "max_solver_step_s": 1.0e-4,
            "method": "BDF",
            "jacobian": "analytic",
        }
    )
    raw["vehicle"]["travel_speed_m_s"] = speed_kmh / 3.6
    raw.pop("initial_state", None)
    target = HERE.parent / "scratch" / "s56" / "case.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw), encoding="utf-8")

    case = load_vehicle_case(target)
    dynamics = VehicleDynamics(case)
    y_index = int(dynamics.topology.require("wheelset1", "y"))
    yaw_index = int(dynamics.topology.require("wheelset1", "yaw"))
    dynamics.close()

    rows: list[tuple[float, float]] = []

    def record(t_s, rail_id, bodies) -> None:
        if not rail_id.startswith("axle1_"):
            return
        total = sum(force for body_id, force in bodies if body_id.endswith("blade"))
        rows.append((float(t_s), float(total)))

    saved = solver_module.BODY_CONTACT_HOOK
    solver_module.BODY_CONTACT_HOOK = record
    try:
        result = simulate_vehicle(case)
    finally:
        solver_module.BODY_CONTACT_HOOK = saved

    times = np.asarray(result.times_s, dtype=float)
    positions = np.asarray(result.positions, dtype=float)
    speed = speed_kmh / 3.6
    axle = x_start + 10.0 + times * speed
    y = positions[:, y_index]
    yaw = positions[:, yaw_index]

    first = next(((t_s, force) for t_s, force in rows if force > 0.0), None)
    if first is None:
        frame = int(np.argmin(np.abs(axle - ONSET_AT_M)))
        return {
            "x_start": x_start,
            "speed_kmh": speed_kmh,
            "touched": False,
            "axle_at_closest": float(axle[frame]),
            "y_mm_at_closest": float(y[frame]) * 1.0e3,
            "yaw_mrad_at_closest": float(yaw[frame]) * 1.0e3,
            "y_range_mm": [float(y.min()) * 1.0e3, float(y.max()) * 1.0e3],
            "frames": int(times.size),
            "status": (result.summary or {}).get("status"),
        }

    t_onset, force = first
    frame = int(np.argmin(np.abs(times - t_onset)))
    return {
        "x_start": x_start,
        "speed_kmh": speed_kmh,
        "touched": True,
        "t_onset_s": t_onset,
        "axle_at_onset": float(x_start + 10.0 + t_onset * speed),
        "onset_error_m": float(x_start + 10.0 + t_onset * speed - ONSET_AT_M),
        "force_kn": force / 1.0e3,
        "y_mm": float(y[frame]) * 1.0e3,
        "yaw_mrad": float(yaw[frame]) * 1.0e3,
        "y_range_mm": [float(y.min()) * 1.0e3, float(y.max()) * 1.0e3],
        "frames": int(times.size),
        "status": (result.summary or {}).get("status"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    parser.add_argument("--entries", type=float, nargs="+", default=[52.0, 62.0])
    parser.add_argument("--duration", type=float, default=0.34)
    args = parser.parse_args()

    out = []
    for entry in args.entries:
        # Keep the window proportional so every entry reaches the criterion mileage plus a margin.
        need = (ONSET_AT_M + 0.6 - (entry + 10.0)) / (args.speed_kmh / 3.6)
        duration = float(min(args.duration, max(0.08, need)))
        print(f"entry {entry:.1f} m  {args.speed_kmh:.1f} km/h  window {duration:.3f} s", flush=True)
        row = one(x_start=entry, speed_kmh=args.speed_kmh, duration_s=duration)
        print("   " + json.dumps(row, ensure_ascii=False), flush=True)
        out.append(row)

    target = HERE.parent / "scratch" / "s56" / "onset_2d.json"
    target.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\nwrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
