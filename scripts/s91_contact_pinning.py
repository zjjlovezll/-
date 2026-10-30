"""Which candidate pins the contact point? (1) frame shift, (3) search window, (2) flange argmin.

Shifting a wheelset laterally by 4 mm must move the contact point by roughly the same 4 mm along the
profile.  Measured, it moves ~0.7 mm and the contact is lost within 1 mm, so the contact point is
pinned by something.  This script records what each candidate predicts, in that order:

1. frame -- are the wheel band and the rail band moving together?  Recorded by wrapping
   ``_absolute_arrays``: wheel centre y, wheel lateral offset, rail y, both bands' ranges, overlap.
2. window -- does ``patch_window_m`` (default 1 mm) clip the engaged run?  Reproduced with the window
   widened to 10 mm.  Diagnostic only: the repair is a window that follows the wheel, not a bigger
   window.
3. flange -- is the deepest point the flange tip rather than the tread?  Classified by the
   lateral position of the joint minimum (|y| < 60 mm is tread, further out is flange).

Nothing is written to the repository config; the case is copied under scratch/.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

import velch.contact as contact_module
import velch.contact_search as search_module
from velch.data_root import case_dir
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat

RECORDS: list[dict[str, float]] = []
_ORIGINAL = search_module._absolute_arrays


def _recording(wheel_profile, rail_sample, *, wheel_y_m, wheel_z_m, wheel_roll_rad,
               wheel_lateral_offset_m, rail_y_m, rail_z_m):
    wheel_y, wheel_z, rail_y, rail_z = _ORIGINAL(
        wheel_profile, rail_sample,
        wheel_y_m=wheel_y_m, wheel_z_m=wheel_z_m, wheel_roll_rad=wheel_roll_rad,
        wheel_lateral_offset_m=wheel_lateral_offset_m, rail_y_m=rail_y_m, rail_z_m=rail_z_m,
    )
    lo = max(float(wheel_y.min()), float(rail_y.min()))
    hi = min(float(wheel_y.max()), float(rail_y.max()))
    index = int(np.argmin(rail_z - np.interp(wheel_y, rail_y, rail_z)))
    RECORDS.append({
        "wheel_y_m": float(wheel_y_m),
        "wheel_lateral_offset_m": float(wheel_lateral_offset_m),
        "rail_y_m": float(rail_y_m),
        "wheel_band_lo": float(wheel_y.min()),
        "wheel_band_hi": float(wheel_y.max()),
        "rail_band_lo": float(rail_y.min()),
        "rail_band_hi": float(rail_y.max()),
        "overlap_lo": lo,
        "overlap_hi": hi,
        "overlap_width": max(hi - lo, 0.0),
        "deepest_y": float(wheel_y[index]),
        "roll": float(wheel_roll_rad),
    })
    return wheel_y, wheel_z, rail_y, rail_z


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default=str(case_dir() / "case_A_plain.json"))
    parser.add_argument("--window-mm", type=float, default=None, help="override patch_window_m")
    parser.add_argument("--shifts-mm", default="0,1,2,4")
    parser.add_argument("--wheel-offset-mm", type=float, default=None,
                        help="override the lateral position of every wheel (registration test)")
    options = parser.parse_args()

    search_module._absolute_arrays = _recording
    if hasattr(contact_module, "_absolute_arrays"):
        contact_module._absolute_arrays = _recording

    raw = json.loads(Path(options.case).read_text(encoding="utf-8"))
    if options.wheel_offset_mm is not None:
        for wheel in raw["wheels"]:
            wheel["lateral_offset_m"] = math.copysign(abs(options.wheel_offset_mm) * 1e-3,
                                                      float(wheel["lateral_offset_m"]))
    if options.window_mm is not None:
        raw["contact"]["patch_window_m"] = options.window_mm * 1e-3
    scratch = Path(__file__).resolve().parents[2] / "scratch" / "s91"
    scratch.mkdir(parents=True, exist_ok=True)
    tag = f"window{options.window_mm}_off{options.wheel_offset_mm}"
    target = scratch / f"{Path(options.case).stem}_{tag}.json"
    target.write_text(json.dumps(raw), encoding="utf-8")

    case = load_vehicle_case(target)
    dynamics = VehicleDynamics(case)
    q = np.array(case.initial_q, dtype=float)
    velocity = np.array(case.initial_v, dtype=float)
    seated, residual = _seat(case, dynamics, q, velocity)
    speed = float(case.vehicle.travel_speed_m_s)
    for body in dynamics.topology.bodies:
        if body.id.startswith("wheelset") and "spin" in body.dof:
            velocity[dynamics.topology.require(body.id, "spin")] = speed / case.vehicle.nominal_wheel_radius_m

    print(f"case {Path(options.case).name} window {options.window_mm} mm seat residual {residual:.2e} N")
    wheelsets = [b for b in dynamics.topology.bodies if b.id.startswith("wheelset")]
    print(f"{'shift(mm)':>9s} {'rail_y_m':>9s} {'wheel_off':>10s} {'overlap(mm)':>12s} "
          f"{'deepest_y(mm)':>14s} {'lever_y(mm)':>12s} {'pen(um)':>9s} {'N(kN)':>8s}")
    baseline_lever: float | None = None
    for shift_mm in [float(s) for s in options.shifts_mm.split(",") if s.strip()]:
        state = seated.copy()
        for body in wheelsets:
            state[dynamics.topology.require(body.id, "y")] += shift_mm * 1e-3
        RECORDS.clear()
        _forces, contacts = dynamics.evaluate(0.0, state, velocity)
        response = contacts.get("axle1_left")
        record = RECORDS[-1] if RECORDS else {}
        geometry = response.geometry if response is not None else None
        lever = float(geometry.lever_y_m) if geometry is not None else float("nan")
        if baseline_lever is None:
            baseline_lever = lever
        print(f"{shift_mm:9.2f} {record.get('rail_y_m', float('nan')):9.6f} "
              f"{record.get('wheel_lateral_offset_m', float('nan')):10.6f} "
              f"{1e3 * record.get('overlap_width', float('nan')):12.3f} "
              f"{1e3 * record.get('deepest_y', float('nan')):14.3f} "
              f"{1e3 * lever:12.4f} "
              f"{1e6 * (geometry.penetration_m if geometry else float('nan')):9.2f} "
              f"{(response.normal_force_n if response else 0.0) / 1e3:8.2f}")
        if geometry is not None and abs(shift_mm) > 0.0:
            print(f"          d(lever)/d(shift) = {(lever - baseline_lever) / (shift_mm * 1e-3):+.3f} m/m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
