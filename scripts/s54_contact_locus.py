"""Is the contact lateral position outside the rail head, or was the yardstick wrong?

B045 was registered as "the contact sits outside the rail head on the curved route", by comparing the
reported ``lever_y`` (+0.899 / +1.007 m) with a head band of about 0.743-0.815 m.  That band was measured
at the *straight* section, where the right rail sits at +0.753 m.  On the diverging route the rail itself
moves outwards -- the station table carries ``y_offset_m`` per station -- so the yardstick has to be taken
at the axle's **own mileage**, not at the start of the case.

This script does exactly that and nothing else (no simulation): for a given final state it samples each
rail at the mileage that axle actually reached, reads the rail's own lateral extent, and reports whether
``lever_y`` falls inside it.

Run::

    PYTHONPATH=src python -X utf8 scripts/s54_contact_locus.py --x-start 52 --travelled 7.11
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
CASE = HERE.parent / "scratch" / "s52" / "case_two_body_switch.json"

# lever_y of the last frame of the 0.32 s passage (`--duration 0.32`, round 216), kN and micrometres.
MEASURED = {
    "axle1_left": (71.79, 75.43, -0.59610),
    "axle1_right": (47.38, 34.13, +0.91038),
    "axle2_left": (69.26, 69.06, -0.63499),
    "axle2_right": (50.11, 56.08, +0.87571),
    "axle3_left": (59.74, 62.61, -0.75130),
    "axle3_right": (59.62, 67.91, +0.75284),
    "axle4_left": (59.70, 62.39, -0.75159),
    "axle4_right": (59.66, 67.94, +0.75252),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, default=CASE)
    parser.add_argument("--x-start", type=float, default=52.0)
    parser.add_argument("--travelled", type=float, default=7.11)
    args = parser.parse_args()

    from velch.vehicle import load_vehicle_case

    case = load_vehicle_case(args.case)
    axle_offsets = tuple(float(v) for v in case.vehicle.axle_offsets_m)
    origin = args.x_start + args.travelled
    rails = {rail.id: rail for rail in case.rails}
    print(f"origin {origin:.2f} m   (x_start {args.x_start:.2f} + travelled {args.travelled:.2f})")
    print(f"axle offsets (front to rear): {axle_offsets}")
    print()
    print("  rail          mileage    head band (absolute y)              lever_y    inside")
    worst = 0.0
    for rail_id, (force_kn, pen_um, lever_y) in sorted(MEASURED.items()):
        axle = int(rail_id.split("_")[0].removeprefix("axle"))
        mileage = origin + axle_offsets[axle - 1]
        rail = rails[rail_id]
        # `VehicleRail` exposes `bodies`; each body carries its own series (`RailBody.series`).
        body = next(
            (b for b in rail.bodies if b.s_lo_m is None or b.s_lo_m - 1.0e-9 <= mileage <= (b.s_hi_m or 1e9)),
            rail.bodies[0],
        )
        sample = body.series.sample(mileage, 1.0)
        y = np.asarray(sample.profile.y_m, dtype=float)
        z = np.asarray(sample.profile.z_m, dtype=float)
        crown = float(np.max(z))
        head = y[z >= crown - 1.0e-3]
        low, high = float(head.min()), float(head.max())
        inside = low <= lever_y <= high
        if not inside:
            worst = max(worst, min(abs(lever_y - low), abs(lever_y - high)))
        print(f"  {rail_id:13s} {mileage:7.2f}  [{low:+.4f}, {high:+.4f}]  "
              f"(width {(high - low) * 1.0e3:5.1f} mm)  {lever_y:+.5f}   "
              f"{'yes' if inside else 'NO'}   N {force_kn:5.2f} kN  pen {pen_um:6.2f} um")
    print()
    if worst == 0.0:
        print("VERDICT: every contact lies inside its own rail head at its own mileage --")
        print("         the 'outside the head' reading came from a band taken at another mileage")
        return 0
    print(f"VERDICT: at least one contact is outside its rail head by up to {worst * 1.0e3:.1f} mm")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
