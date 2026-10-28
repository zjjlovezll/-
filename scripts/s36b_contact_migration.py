"""Does the contact point migrate laterally as the rail surface moves up and down?

Why this is asked: `scripts/s35_straight_random_speed.py` measured that the transfer from applied
depth to axle-box acceleration is not proportional to the depth, and that the drift runs in
*opposite directions* in different wavelength bands (0.1004 m loses a factor of 8 between 0.1 and
0.3 mm peak-to-peak, while 0.2293 m gains 1.6x).  A wheel that never leaves the rail (0.0 % of the
window, measured) can still change its *contact point* along the tread when the rail surface rises:
the tread is curved, so the deepest point slides sideways as the rail moves vertically.  If it
does, the lever arms that feed the creep law move with the corrugation amplitude, which is a
geometric reason for an amplitude-dependent transfer -- no contact loss required.

The measurement is static: seat the straight case once, then ask `find_patch_contact` for the same
wheel against the same rail raised and lowered by up to +-150 um, and read lever_y, lever_z,
penetration and the normal direction.  Nothing is integrated, so this is seconds, and it tests the
mechanism directly instead of inferring it from a gain table.

Usage:
    PYTHONPATH=src python -X utf8 scripts/s36b_contact_migration.py
"""

from __future__ import annotations

import argparse
import math
from dataclasses import replace
from pathlib import Path

import numpy as np

from velch.contact_search import find_patch_contact
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat

BASE_CASE = Path("F:/velch_data/validation/crh380a_m/case_A_final_law.json")
MILEAGE_M = 44.0
OFFSETS_UM = (-150.0, -100.0, -50.0, 0.0, 50.0, 100.0, 150.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mileage", type=float, default=MILEAGE_M)
    args = parser.parse_args(argv)

    case = load_vehicle_case(BASE_CASE)
    dynamics = VehicleDynamics(case)
    speed = abs(case.vehicle.travel_speed_m_s)
    q = np.zeros(dynamics.dimension)
    v = np.zeros(dynamics.dimension)
    for body in dynamics.topology.bodies:
        if "spin" in body.dof:
            v[dynamics.topology.require(body.id, "spin")] = speed / 0.43
    seated, residual = _seat(case, dynamics, q, v)
    print(f"seated on the straight baseline: residual {residual:.3e} N")

    rail = next(item for item in case.rails if str(item.id) == "axle1_left")
    wheel = next(item for item in case.wheels if str(item.id) == "L")
    sample = rail.bodies[0].series.sample(args.mileage, 1.0)
    base = sample.profile
    wheel_profile = dynamics._deformed_profile(wheel, rail, seated)
    rail_index = next(index for index, item in enumerate(case.rails)
                      if str(item.id) == "axle1_left")
    rail_y, rail_z, _, _ = dynamics.track.local_state(seated, v, rail_index, args.mileage, speed)
    wheel_y = float(seated[dynamics.topology.require("wheelset1", "y")])
    wheel_z = float(case.vehicle.wheel_center_height_m + seated[dynamics.topology.require(
        "wheelset1", "z")])
    wheel_roll = float(seated[dynamics.topology.require("wheelset1", "roll")])
    print(f"wheel y {wheel_y:+.6f} z {wheel_z:+.6f} roll {wheel_roll:+.6f}; "
          f"rail y {rail_y:+.6f} z {rail_z:+.6f}")

    # Faithfulness check: the same wheel and mileage through the solver's own path, so the probe's
    # zero-offset row can be compared with the value the dynamics actually uses.  A difference in
    # the contact policy (patch window, grid step) would show up here as a different lever_y.
    t_probe = (args.mileage - case.run.x_start_m) / speed
    _, contacts = dynamics.evaluate(t_probe, seated, v)
    reference = contacts.get("axle1_left")
    if reference is not None and reference.geometry is not None:
        print(f"reference (evaluate) at {args.mileage:.1f} m: lever_y "
              f"{reference.geometry.lever_y_m:+.6f}, lever_z {reference.geometry.lever_z_m:+.6f}, "
              f"penetration {reference.geometry.penetration_m * 1e6:.3f} um")

    print("\n rail raised   lever_y (m)  lever_z (m)   penetration (um)   n_y      n_z")
    rows = []
    for offset in OFFSETS_UM:
        shifted = replace(base, z_m=base.z_m + offset * 1e-6)
        shifted_sample = replace(sample, profile=shifted)
        geometry = find_patch_contact(
            wheel_profile, shifted_sample,
            wheel_y_m=wheel_y,
            wheel_z_m=wheel_z,
            wheel_roll_rad=wheel_roll,
            wheel_lateral_offset_m=wheel.lateral_offset_m,
            rail_y_m=rail_y,
            rail_z_m=rail_z,
            window_m=1.0e-3,
            iterations=3,
        )
        if geometry is None:
            print(f" {offset:+8.1f} um   no contact")
            rows.append((offset, None))
            continue
        print(f" {offset:+8.1f} um   {geometry.lever_y_m:+.6f}     {geometry.lever_z_m:+.6f}"
              f"    {geometry.penetration_m * 1e6:9.3f}        {geometry.normal_y:+.4f}"
              f"  {geometry.normal_z:+.4f}")
        rows.append((offset, geometry))

    valid = [(offset, geometry) for offset, geometry in rows if geometry is not None]
    if len(valid) >= 2:
        offsets = np.array([item[0] for item in valid]) * 1e-6
        lever_y = np.array([item[1].lever_y_m for item in valid])
        lever_z = np.array([item[1].lever_z_m for item in valid])
        slope_y = float(np.polyfit(offsets, lever_y, 1)[0])
        slope_z = float(np.polyfit(offsets, lever_z, 1)[0])
        span_y = float(lever_y.max() - lever_y.min()) * 1e6
        span_z = float(lever_z.max() - lever_z.min()) * 1e6
        print(f"\n migration: d(lever_y)/d(rail z) = {slope_y:+.4f} m/m, "
              f"span over the sweep {span_y:.1f} um")
        print(f"            d(lever_z)/d(rail z) = {slope_z:+.4f} m/m, "
              f"span over the sweep {span_z:.1f} um")
        # A contact that slides sideways changes the rolling radius through the tread slope, so
        # the predicted rolling-radius change is slope_y * d(rail z).  Print it so the number can
        # be compared with the 96 um the 2 mm lateral shift produced in s34.
        print(f"            rolling radius change across the sweep: {span_y * 0.048:.3f} um "
              f"(tread slope 0.048)")
        if abs(span_y) < 10.0:
            print("  reading: the contact point does NOT migrate by more than 10 um over "
                  "+-150 um of rail height -- contact migration cannot explain the "
                  "amplitude-dependent transfer.")
        else:
            print("  reading: the contact point DOES migrate laterally with rail height; "
                  "this is a geometric source of amplitude-dependent transfer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
