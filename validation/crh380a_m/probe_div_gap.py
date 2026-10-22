"""Why does the left rail report no contact in the double-body case?

Prints, per axle, the wheel's lateral band and each left/right rail body's band, plus the vertical gap
between the two surfaces at the band overlap.  A positive gap means the wheel is above the rail (no
contact), which is a geometry/placement question, not a solver question.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402


def main(path: str) -> int:
    case = load_vehicle_case(HERE / path)
    wheels = {wheel.id: wheel for wheel in case.wheels}
    print(f"case {case.case_id}\n")
    for rail in case.rails:
        wheel = wheels[rail.wheel_id]
        station = case.run.x_start_m + case.vehicle.axle_offsets_m[rail.axle_index]
        lateral = case.path.at(station)
        wheel_band = wheel.profile
        wheel_y = wheel.lateral_offset_m + lateral + wheel_y_offsets(wheel_band)
        wheel_z = case.wheel_center_height_m + wheel_band.z_m
        bodies = getattr(rail, "contact_bodies", None) or []
        print(f"{rail.id:<14} wheel_id={rail.wheel_id} station={station:7.3f} "
              f"wheel y {wheel_y.min()*1e3:7.1f}..{wheel_y.max()*1e3:7.1f} mm")
        if not bodies:
            sample = rail.series.sample(station, 1)
            profile = getattr(sample, "profile", sample)
            print(f"{'':14} single body  y {profile.y_m.min()*1e3:7.1f}.."
                  f"{profile.y_m.max()*1e3:7.1f} mm  z {profile.z_m.min()*1e3:7.2f}.."
                  f"{profile.z_m.max()*1e3:7.2f} mm")
            continue
        for body in bodies:
            if not body.active_at(station):
                print(f"{'':14} {body.id:<7} inactive")
                continue
            sample = body.series.sample(station, 1)
            profile = getattr(sample, "profile", sample)
            overlap_lo = max(profile.y_m.min(), wheel_y.min())
            overlap_hi = min(profile.y_m.max(), wheel_y.max())
            if overlap_hi <= overlap_lo:
                print(f"{'':14} {body.id:<7} y {profile.y_m.min()*1e3:7.1f}.."
                      f"{profile.y_m.max()*1e3:7.1f} mm  no lateral overlap")
                continue
            grid = np.linspace(overlap_lo, overlap_hi, 401)
            rail_z = np.interp(grid, profile.y_m, profile.z_m)
            wheel_local = grid - wheel.lateral_offset_m - lateral
            wheel_zg = case.wheel_center_height_m + np.interp(wheel_local, wheel_band.y_m,
                                                              wheel_band.z_m)
            gap = wheel_zg - rail_z
            print(f"{'':14} {body.id:<7} y {profile.y_m.min()*1e3:7.1f}.."
                  f"{profile.y_m.max()*1e3:7.1f} mm  z {profile.z_m.min()*1e3:7.2f}.."
                  f"{profile.z_m.max()*1e3:7.2f}  min gap {gap.min()*1e3:7.2f} mm "
                  f"at y {grid[int(gap.argmin())]*1e3:7.1f}")
        print()
    return 0


def wheel_y_offsets(profile) -> np.ndarray:
    return np.asarray(profile.y_m, dtype=float)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
