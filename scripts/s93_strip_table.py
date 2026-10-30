"""Check the strip model's own normal stiffness against the measured lateral response.

``find_strip_contact`` (``src/velch/contact_search.py:518-700``) integrates the
plane-strain line load ``n = (pi/4) E* delta`` over every engaged strip, then reports an
*equivalent* penetration ``delta_eq = (N / C) ** (2/3)`` so that the rest of the chain
(damping, friction saturation, history) keeps running on a single number.  Two things
follow, and they are the whole point of this script:

* ``dN/d(delta_eq) = 1.5 N / delta_eq`` **by construction**, so the model is not judged by
  comparing that slope with a point-Hertz slope at the *geometric* depth: 197.6 um of
  equivalent penetration and 65.47 um of oracle penetration are the same 59.68 kN *by
  definition of the equivalent depth*, not a discrepancy;
* the force is **linear** in strip depth, ``N = (pi/4) E* sum(delta_i) dy``, so a lateral
  shift changes the force through how many strips stay engaged as much as through their
  depth.

An earlier note in ``docs/STRAIGHT_LATERAL_B047_2026-10-29.md`` said the measured
stiffness was 1100x softer than Hertz.  That was a unit slip -- kN/mm divided by mm/mm is
kN/mm, not kN/um -- and the numbers below are what make the arithmetic checkable without
any grid reconstruction.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from velch.data_root import case_dir
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat


EVEN_SHARE_N = 59_662.0


def sweep(case, speed: float, shifts_mm: tuple[float, ...]) -> dict[str, float]:
    dynamics = VehicleDynamics(case)
    q0 = np.zeros(dynamics.dimension)
    velocity = np.zeros(dynamics.dimension)
    for body in dynamics.topology.bodies:
        try:
            velocity[dynamics.topology.require(body.id, "spin")] = speed / float(
                case.vehicle.nominal_wheel_radius_m)
        except Exception:
            pass
    seated, residual = _seat(case, dynamics, q0, velocity)

    rows = []
    for shift_mm in shifts_mm:
        state = np.array(seated, dtype=float)
        for body in dynamics.topology.bodies:
            if body.id.startswith("wheelset"):
                try:
                    state[dynamics.topology.require(body.id, "y")] += shift_mm * 1e-3
                except Exception:
                    pass
        dynamics.evaluate(0.0, state, velocity)
        entry = next((e for e in dynamics.body_contacts.get("axle1_left", ())
                      if e.geometry is not None), None)
        if entry is None:
            rows.append({"shift_mm": shift_mm, "loaded": 0})
            continue
        rows.append(
            {
                "shift_mm": shift_mm,
                "loaded": 1,
                "lever_mm": 1e3 * entry.geometry.lever_y_m,
                "pen_um": 1e6 * entry.geometry.penetration_m,
                "normal_kn": entry.normal_force_n / 1e3,
            }
        )
    return {"residual_n": residual, "rows": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="case_A_plain.json")
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    parser.add_argument("--shifts-mm", type=float, nargs="+", default=[0.0, 2.0])
    options = parser.parse_args(argv)

    case = load_vehicle_case(case_dir() / options.case)
    result = sweep(case, options.speed_kmh / 3.6, tuple(options.shifts_mm))
    print(f"case {options.case}  seat residual {result['residual_n']:.3e} N")
    print("  shift(mm)  lever_y(mm)  pen(um)  normal(kN)   1.5N/pen (kN/mm)")
    for row in result["rows"]:
        if not row.get("loaded"):
            print(f"  {row['shift_mm']:9.2f}  (no contact)")
            continue
        slope = 1.5 * row["normal_kn"] / row["pen_um"] * 1e3  # kN/um -> kN/mm
        print(f"  {row['shift_mm']:9.2f}  {row['lever_mm']:11.3f}  {row['pen_um']:7.2f}  "
              f"{row['normal_kn']:10.3f}   {slope:12.1f}")

    loaded = [r for r in result["rows"] if r.get("loaded")]
    if len(loaded) >= 2:
        first, last = loaded[0], loaded[-1]
        dn_dy = (last["normal_kn"] - first["normal_kn"]) / (last["shift_mm"] - first["shift_mm"])
        dpen_dy = (last["pen_um"] - first["pen_um"]) / (last["shift_mm"] - first["shift_mm"])
        print(f"\nd(normal)/d(y)   = {dn_dy:+.3f} kN/mm")
        print(f"d(penetration)/d(y) = {dpen_dy:+.3f} um/mm")
        if abs(dpen_dy) > 0.0:
            print(f"measured dN/d(pen) = {dn_dy / dpen_dy * 1e3:+.1f} kN/mm   "
                  f"(kN/mm over um/mm = 1e3 kN/mm)")
        print(f"model 1.5N/pen at the seated state = "
              f"{1.5 * first['normal_kn'] / first['pen_um'] * 1e3:.1f} kN/mm")
        print("\nThe two must agree: they are the same state read two ways.  A point-Hertz "
              "slope\nat the *geometric* depth is a different quantity and is not comparable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
