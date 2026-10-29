"""Split the 0.32 mm blade-gap deficit into "rail is lowered less than the design table says" and
"the wheel surface at the blade's lateral position is not at the stock contact height".

Round 220 measured the blade onset statically at 68.80 m with the wheelset centric, while the
mileage-only form (lowering = 65.47 um) predicts 68.158 m -- 0.642 m x 0.5 mm/m = 0.32 mm of gap that the
form does not account for.  This reads that 0.32 mm out of the geometry itself, with no run:

  * crown-to-crown: stock crown z minus blade crown z at the same mileage (the lowering the geometry
    actually carries), against the design table value;
  * wheel surface: the wheel profile height at the blade's lateral position against its height at the
    stock contact position -- the term the form implicitly assumes is zero.

    PYTHONPATH=src python -X utf8 scripts/s58_blade_gap_decompose.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
CASE = HERE.parent / "scratch" / "s52" / "case_two_body_switch.json"
TIP_M = 60.95
STATIC_PENETRATION_UM = 65.47


def crown(sample) -> tuple[float, float]:
    z = np.asarray(sample.profile.z_m, dtype=float)
    y = np.asarray(sample.profile.y_m, dtype=float)
    index = int(np.argmax(z))
    return float(y[index]), float(z[index])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mileages", type=float, nargs="+", default=[68.0, 68.2, 68.4, 68.6, 68.8, 69.0])
    args = parser.parse_args()

    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics

    # No seat and no integration: this only reads the two rail surfaces and the wheel profile.
    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)

    wheel = None
    for candidate in case.wheels:
        if candidate.lateral_offset_m > 0.0:
            wheel = candidate
            break
    if wheel is None:
        raise SystemExit("no right-hand wheel in the case")
    wheel_y = np.asarray(wheel.profile.y_m, dtype=float)
    wheel_z = np.asarray(wheel.profile.z_m, dtype=float)
    print(f"wheel offset {wheel.lateral_offset_m:+.4f} m   profile y {wheel_y[0]:+.4f}..{wheel_y[-1]:+.4f} m   "
          f"z {wheel_z.min():+.4f}..{wheel_z.max():+.4f} m")

    rows = []
    print(f"\n{'mileage':>8} {'stock crown':>22} {'blade crown':>22} {'lowering':>10} {'design':>8} "
          f"{'wheel@blade':>12} {'wheel@stock':>12} {'gap':>9}")
    for mileage in args.mileages:
        per_body: dict[str, tuple[float, float]] = {}
        for rail in case.rails:
            if not str(rail.id).startswith("axle1_right"):
                continue
            bodies = getattr(rail, "bodies", None) or ()
            for body in bodies:
                series = getattr(body, "series", None)
                if series is None:
                    continue
                sample = series.sample(float(mileage), 1.0)
                per_body[str(body.id)] = crown(sample)
        stock = next((value for key, value in per_body.items() if key.endswith("stock")), None)
        blade = next((value for key, value in per_body.items() if key.endswith("blade")), None)
        if stock is None or blade is None:
            print(f"{mileage:8.2f}   bodies {sorted(per_body)}")
            continue
        lowering = stock[1] - blade[1]
        design = 0.5e-3 * max(TIP_M + 6.569 - mileage, 0.0) / 0.735
        # Wheel surface height at each lateral position, measured from the wheel centre.
        at_stock = float(np.interp(stock[0] - wheel.lateral_offset_m, wheel_y, wheel_z))
        at_blade = float(np.interp(blade[0] - wheel.lateral_offset_m, wheel_y, wheel_z))
        gap = (at_blade - at_stock) - lowering
        rows.append(
            {
                "mileage_m": float(mileage),
                "stock_crown_y_m": stock[0],
                "stock_crown_z_m": stock[1],
                "blade_crown_y_m": blade[0],
                "blade_crown_z_m": blade[1],
                "lowering_m": lowering,
                "design_lowering_m": design,
                "wheel_at_blade_rel_stock_m": at_blade - at_stock,
                "gap_m": gap,
            }
        )
        print(f"{mileage:8.2f} {stock[0]:+9.4f}/{stock[1]:+9.5f} {blade[0]:+9.4f}/{blade[1]:+9.5f} "
              f"{lowering * 1.0e3:10.3f} {design * 1.0e3:8.3f} {at_blade * 1.0e3:12.3f} "
              f"{at_stock * 1.0e3:12.3f} {gap * 1.0e6:9.1f}")

    dynamics.close()
    out = HERE.parent / "scratch" / "s58" / "decompose.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": rows, "static_penetration_um": STATIC_PENETRATION_UM}, indent=1),
                   encoding="utf-8")
    print(f"\n(lowering / design in mm, wheel heights in mm from the wheel centre, gap in um)")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
