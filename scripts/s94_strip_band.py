"""One patch's strip table, taken from the solver itself.

This is the diagnostic half of the SDITT alignment.  ``NF_STRIPES_230623.m`` keeps two
quantities apart that ``strip_integral`` merges into one: the *virtual penetration region*
(``h_0 = eps * delta``, ``eps = n^2/r/(1+(n/m)^2)`` from the transverse radii ``m``, ``n``
and the rolling radius ``r``) and the *strip sum* over that region.  Our
``find_strip_contact`` integrates only the second and reports a single equivalent
penetration, so the band -- how wide it is, where its centroid sits, how deep the deepest
strip is -- has never been visible.

``contact_search.STRIP_DIAGNOSTIC`` was added for exactly this: a collector that receives
``(center_y, grid, depth, engaged, step, force)`` per patch and is ``None`` on every
production path.  With it this script prints the table and, side by side, the SDITT
``eps`` computed from the curvatures the strip code already fits at the contact.

Readings of interest:

* band width and peak depth: a 300 mm crown under a 59.7 kN wheel should give a band of
  order ``sqrt(8 R delta)`` = 7 mm at ``delta`` = 200 um;
* ``eps``: if ``eps << 1`` (it is ~0.1 for tread-on-crown), then SDITT's force responds to
  ``eps * delta`` and ours responds to ``delta`` -- i.e. ours is *stiffer* than theirs by
  ``1/eps`` before any calibration, which is the direction that matters for the curve;
* the centroid vs the deepest strip: if they differ by millimetres the reported lateral
  position is a band average, not a contact point, and no "contact point follows the
  wheel 1:1" statement should be read from it alone.
"""

from __future__ import annotations

import argparse
import math
import sys

import numpy as np

from velch import contact_search
from velch.data_root import case_dir
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="case_A_plain.json")
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    parser.add_argument("--shift-mm", type=float, default=0.0)
    options = parser.parse_args(argv)

    case = load_vehicle_case(case_dir() / options.case)
    dynamics = VehicleDynamics(case)
    velocity = np.zeros(dynamics.dimension)
    speed = options.speed_kmh / 3.6
    for body in dynamics.topology.bodies:
        try:
            velocity[dynamics.topology.require(body.id, "spin")] = speed / float(
                case.vehicle.nominal_wheel_radius_m)
        except Exception:
            pass
    seated, residual = _seat(case, dynamics, np.zeros(dynamics.dimension), velocity)

    state = np.array(seated, dtype=float)
    if options.shift_mm:
        for body in dynamics.topology.bodies:
            if body.id.startswith("wheelset"):
                try:
                    state[dynamics.topology.require(body.id, "y")] += options.shift_mm * 1e-3
                except Exception:
                    pass

    collected: list[dict[str, object]] = []

    def collect(center_y, grid, depth, engaged, step, force) -> None:
        mask = np.asarray(engaged, dtype=bool)
        d = np.asarray(depth, dtype=float)[mask]
        g = np.asarray(grid, dtype=float)[mask]
        collected.append(
            {
                "center_y_m": float(center_y),
                "strips": int(d.size),
                "step_m": float(step),
                "width_m": float(d.size * step),
                "peak_um": 1e6 * float(d.max()),
                "centroid_mm": 1e3 * float(np.sum(g * d) / np.sum(d)),
                "deepest_mm": 1e3 * float(g[int(np.argmax(d))]),
                "sum_depth_dy": float(np.sum(d) * step),
                "force_n": float(force),
            }
        )

    contact_search.STRIP_DIAGNOSTIC = collect
    try:
        dynamics.evaluate(0.0, state, velocity)
    finally:
        contact_search.STRIP_DIAGNOSTIC = None

    print(f"case {options.case}  seat residual {residual:.3e} N  "
          f"patches collected {len(collected)}  shift {options.shift_mm:+.2f} mm")
    if not collected:
        print("no strip patch reported")
        return 1
    print("\n  #  centre_y(mm)  strips  width(mm)  peak(um)  centroid(mm)  deepest(mm)  "
          "force(kN)")
    for index, row in enumerate(collected[:8]):
        print(f"  {index:2d}  {1e3*row['center_y_m']:12.4f}  {row['strips']:6d}  "
              f"{1e3*row['width_m']:9.4f}  {row['peak_um']:8.2f}  {row['centroid_mm']:11.4f}  "
              f"{row['deepest_mm']:10.4f}  {row['force_n']/1e3:8.3f}")

    first = collected[0]
    spacing = float(first["step_m"])
    width = float(first["width_m"])
    peak = float(first["peak_um"])
    print(f"\nfirst patch: {first['strips']} strips x {1e3*spacing:.3f} mm = "
          f"{1e3*width:.3f} mm band, peak depth {peak:.2f} um")
    print(f"  centroid - deepest = {float(first['centroid_mm']) - float(first['deepest_mm']):+.4f} mm"
          "   (0 means the band is symmetric about its deepest strip)")
    expected_width = math.sqrt(8.0 * 0.150 * 1e-6 * peak)  # two 300 mm bodies -> R* = 0.150 m
    print(f"  sqrt(8 R* delta) with R* = 0.150 m, delta = {peak:.1f} um -> "
          f"{1e3*expected_width:.3f} mm")

    # SDITT's elastic correction, from the curvatures the strip code already fits.
    wheel_curvature = None
    rail_curvature = None
    for geometry_holder in dynamics.body_contacts.values():
        for entry in geometry_holder:
            if entry.geometry is not None and entry.geometry.curvature_radius_m:
                wheel_curvature = entry.geometry.curvature_radius_m
                break
        if wheel_curvature:
            break
    rolling = float(case.vehicle.nominal_wheel_radius_m)
    if wheel_curvature:
        m = float(wheel_curvature)          # wheel transverse radius
        n = 0.300                           # rail transverse radius (measured 299.6 mm)
        eps = n * n / rolling / (1.0 + (n / m) ** 2)
        print(f"  SDITT eps = n^2/r/(1+(n/m)^2) with n = 0.300 m, m = {m:.3f} m, "
              f"r = {rolling:.3f} m -> {eps:.4f}")
        print(f"  -> their virtual penetration is eps*delta = {eps*peak:.2f} um; "
              f"ours is delta = {peak:.2f} um")
    else:
        print("  (no curvature radius reported, eps not computed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
