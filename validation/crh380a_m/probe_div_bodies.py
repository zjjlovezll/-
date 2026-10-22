"""Where do the stock / switch / frog bodies actually sit, and does the wheel bridge them?

Prints, per probe station, each active body's lateral band and the wheel's contact band, plus the
overlap with the wheel.  A healthy switch panel shows two bodies ~45 mm apart, both overlapping the
wheel; a bad placement shows them stacked (identical bands) or both far from the wheel.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402

CASE = HERE / "case_diverging_multi.json"
AXLE = 1
PROBES = (53.0, 58.0, 60.0, 60.94, 61.5, 80.0, 104.0, 110.0)


def main() -> int:
    case = load_vehicle_case(CASE)
    wheel = max(case.wheels, key=lambda w: w.lateral_offset_m)  # ids are "L"/"R"
    profile = wheel.profile
    span = case.path.span_m
    print(f"case {case.case_id}: path span {span}, "
          f"path(60 m) = {case.path.at(60.0) * 1e3:.1f} mm\n")
    print(f"{'station':>8} {'body':<7} {'s_lo':>8} {'s_hi':>8} {'band y mm':>18} "
          f"{'overlap mm':>10}")
    for station in PROBES:
        rail = next(r for r in case.rails if r.id == f"axle{AXLE}_right")
        lateral = case.path.at(station)
        wheel_lo = (wheel.lateral_offset_m + lateral + float(profile.y_m.min())) * 1e3
        wheel_hi = (wheel.lateral_offset_m + lateral + float(profile.y_m.max())) * 1e3
        for body in rail.contact_bodies:
            if not body.active_at(station):
                continue
            sample = body.series.sample(station, 1)
            serial = getattr(sample, "profile", sample)
            low = float(serial.y_m.min()) * 1e3
            high = float(serial.y_m.max()) * 1e3
            overlap = max(0.0, min(high, wheel_hi) - max(low, wheel_lo))
            s_lo = "-inf" if body.s_lo_m == float("-inf") else f"{body.s_lo_m:.1f}"
            s_hi = "+inf" if body.s_hi_m == float("inf") else f"{body.s_hi_m:.1f}"
            print(f"{station:8.2f} {body.id:<7} {s_lo:>8} {s_hi:>8} "
                  f"[{low:7.1f},{high:7.1f}] {overlap:10.1f}")
        print(f"{'':8} {'wheel':<7} {'':>8} {'':>8} [{wheel_lo:7.1f},{wheel_hi:7.1f}]")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
