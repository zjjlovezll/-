"""Three numbers that decide why the lowering onset came out 10 m early.

The inversion reported the blade carrying 41.7 kN already at 58.13 m, while the design table says the
blade crown is still 65 um *below* the stock crown there and cannot be touched.  Exactly one of three
things is wrong, and they are separable by reading rather than by re-running the simulation:

1. **the axle labels** -- `axle1_right` and `axle2_right` reported the same mileage (58.127 / 58.128),
   which only happens if `_body_offset_m` returns the same offset for every wheelset;
2. **the blade crown in the database** -- if `crown(blade) - crown(stock)` at a station is not the
   design lowering, the case geometry itself is wrong;
3. **the meaning of the recorded load** -- if both crowns are right and the offsets differ, a loaded
   blade at 58 m means the contact is on something other than the crown.

Prints, for the mileages the inversion disagreed about, the crown of each right-side body, the wheel's
lowest point in the same frame, and the four wheelset offsets.
"""

from __future__ import annotations

import argparse
import pathlib

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _body_offset_m, _seat

CASE = pathlib.Path("vehicles/turnouts/CN60-1100-1_18/cases/straight.json")
STATIONS = (55.0, 58.13, 60.0, 65.0, 68.16, 72.0)


def crown_of_sample(sample) -> tuple[float, float]:
    """Highest point of a sampled section and the lateral position where it sits."""
    z = np.asarray(sample.profile.z_m, dtype=float)
    y = np.asarray(sample.profile.y_m, dtype=float)
    index = int(np.argmin(z))
    return float(z[index]), float(y[index])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    args = parser.parse_args()

    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    q = np.zeros(dynamics.dimension)
    seated, residual = _seat(case, dynamics, q, np.zeros(dynamics.dimension))
    print(f"dimension {dynamics.dimension}, seat residual {residual:.3e} N")

    print("\n-- 1. wheelset longitudinal offsets (must be +10 / +7.5 / -7.5 / -10)")
    for body in dynamics.topology.bodies:
        if not str(getattr(body, "id", "")).startswith("wheelset"):
            continue
        offset = _body_offset_m(case, dynamics.topology, body, seated)
        print(f"   {body.id:12s} offset {offset:+7.3f} m")

    print("\n-- 2. crown of each right-side body against the stock rail")
    right = [rail for rail in case.rails if str(rail.id).startswith("axle1_right")]
    if not right:
        print("   no axle1_right rail found")
        return 1
    rail = right[0]
    bodies = [("main", rail)] + [
        (getattr(body, "id", "?"), body) for body in (getattr(rail, "bodies", None) or ())
    ]
    for station_m in STATIONS:
        print(f"   station {station_m:7.2f} m")
        crowns: dict[str, float] = {}
        for name, holder in bodies:
            series = getattr(holder, "series", None)
            if series is None:
                continue
            try:
                sample = series.sample(station_m, 1.0)
            except Exception as error:  # a body may simply not exist at this mileage
                print(f"      {name:8s} not present ({type(error).__name__})")
                continue
            if sample is None:
                print(f"      {name:8s} no sample")
                continue
            crown, crown_y = crown_of_sample(sample)
            crowns[name] = crown
            print(f"      {name:8s} crown z {crown*1e3:+9.3f} mm at y {crown_y*1e3:+8.3f} mm")
            datum = getattr(sample.profile, "z_offset_m", None)
            if datum is not None:
                print(f"      {'':8s} z_offset {float(datum)*1e3:+9.3f} mm")
        if "main" in crowns and "blade" in crowns:
            lowering = crowns["main"] - crowns["blade"]
            verdict = "yes" if lowering <= 65.47e-6 else "no (crown sits above where the wheel reaches)"
            print(f"      -> lowering (stock - blade) {lowering*1e3:+8.3f} mm   touched? {verdict}")

    print("\n-- 3. wheel lowest point in the same frame as the crowns")
    wheel = case.wheels[1] if len(case.wheels) > 1 else case.wheels[0]
    profile = wheel.profile
    lateral = np.asarray(profile.y_m, dtype=float)
    vertical = np.asarray(profile.z_m, dtype=float)
    datum = float(getattr(profile, "z_offset_m", 0.0) or 0.0)
    lowest = float(np.min(vertical)) + datum
    print(
        f"   wheel R: lateral offset {getattr(wheel, 'lateral_offset_m', 0.0):+.4f} m, "
        f"lowest point z {lowest*1e3:+.3f} mm at y {float(lateral[int(np.argmin(vertical))])*1e3:+.3f} mm"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
