"""B047 candidates 3 and 2: is the lateral stiffening the search window or a rail feature?

``s91`` refuted candidate 1 (the contact point *does* move 1:1 with a lateral shift,
``d(lever_y)/d(shift) = -1.000 m/m``) and refuted the "sitting on the shoulder" story as
well: the local transverse radius at the seated contact is 299.6 mm, i.e. the rail's own
300 mm crown.

What is left is a 3.7x discrepancy: on a 300 mm crown a 2 mm lateral shift should change
the penetration by ``y^2 / (2R) = 6.7 um``, and this model changes it by 50 um.  Two
candidates produce exactly that kind of excess:

3. the search *window* -- ``patch_window_m`` is 1 mm, so the "deepest point" is taken over
   a 1 mm strip and a lateral shift replaces which slice is deepest;
2. a fixed rail *feature* -- if the deepest slice is pinned to one place in the profile
   (a notch, an edge, a kink), moving the wheel changes the value there but not the
   location, and the response is governed by that feature's local curvature instead of the
   crown's.

Both are diagnosed here without touching the physics.  ``patch_window_m`` and
``strip_dy_m`` are law fields (``src/velch/contact_models.py:82`` and ``:85``), so each
variant is a new ``ContactLaw`` on a copy of the case with the *same* seated state.

Pre-registered readings:

* if widening the window to 10 mm collapses the gain towards 7 um/mm, the window is the
  cause (candidate 3) and the repair is in ``find_strip_contact``;
* if the gain is unchanged, the deepest slice is pinned to geometry (candidate 2);
* if refining ``strip_dy_m`` changes the gain materially, the band integral itself is
  under-resolved and nothing else can be concluded before that is fixed.

Diagnostic only: widening a search window is on the forbidden list as a *repair*, so this
script prints and does not change any default.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np

from velch.data_root import case_dir
from velch.vehicle import VehicleCase, load_vehicle_case
from velch.topology import TopologyError
from velch.vehicle_solver import VehicleDynamics, _seat


VARIANTS = (
    ("baseline (window 1 mm, strip 0.25 mm)", {}),
    ("window 10 mm (diagnostic)", {"patch_window_m": 10.0e-3}),
    ("strip 0.10 mm (refined band)", {"strip_dy_m": 1.0e-4}),
)


def _shift(dynamics: VehicleDynamics, q: np.ndarray, shift_m: float) -> np.ndarray:
    """Move every wheelset laterally, leaving the seat otherwise untouched."""

    out = np.array(q, dtype=float)
    for body in dynamics.topology.bodies:
        if not body.id.startswith("wheelset"):
            continue
        try:
            out[dynamics.topology.require(body.id, "y")] += shift_m
        except (KeyError, TopologyError):
            pass
    return out


def _contact(dynamics: VehicleDynamics, q: np.ndarray, rail_id: str = "axle1_left"):
    """First body response of one rail.

    ``body_contacts`` is keyed by rail (``src/velch/vehicle_solver.py:955``) and holds the
    per-body responses; the rail id already says which wheel it belongs to
    (``axle1_left`` is wheelset 1), so there is nothing to match on the response itself.
    """

    for entry in dynamics.body_contacts.get(rail_id, ()):
        if entry.geometry is not None:
            return rail_id, entry
    return rail_id, None


def sweep(case: VehicleCase, speed: float, shifts_m: tuple[float, ...]) -> dict[str, object]:
    dynamics = VehicleDynamics(case)
    q0 = np.zeros(dynamics.dimension, dtype=float)
    velocity = np.zeros(dynamics.dimension, dtype=float)
    for body in dynamics.topology.bodies:
        try:
            spin = dynamics.topology.require(body.id, "spin")
        except (KeyError, TopologyError):
            continue
        velocity[spin] = speed / float(case.vehicle.nominal_wheel_radius_m)
    seated, residual = _seat(case, dynamics, q0, velocity)

    rows: list[dict[str, float]] = []
    points: list[float] = []
    for shift_m in shifts_m:
        state = _shift(dynamics, seated, shift_m)
        dynamics.evaluate(0.0, state, velocity)
        rail_id, entry = _contact(dynamics, state)
        if entry is None:
            rows.append({"shift_mm": 1e3 * shift_m, "loaded": 0})
            continue
        geometry = entry.geometry
        points.append(geometry.lever_y_m)
        rows.append(
            {
                "shift_mm": 1e3 * shift_m,
                "loaded": 1,
                "lever_y_mm": 1e3 * geometry.lever_y_m,
                "penetration_um": 1e6 * geometry.penetration_m,
                "normal_n": entry.normal_force_n,
            }
        )

    gains: dict[str, float] = {}
    if len(points) >= 2:
        gains["d_lever_over_d_shift"] = float(
            (points[-1] - points[0]) / (shifts_m[-1] - shifts_m[0])
        )
    loaded = [row for row in rows if row.get("loaded")]
    if len(loaded) >= 2:
        gains["d_penetration_um_per_mm"] = float(
            (loaded[-1]["penetration_um"] - loaded[0]["penetration_um"])
            / (loaded[-1]["shift_mm"] - loaded[0]["shift_mm"])
        )
        gains["d_normal_kn_per_mm"] = float(
            (loaded[-1]["normal_n"] - loaded[0]["normal_n"]) / 1e3
            / (loaded[-1]["shift_mm"] - loaded[0]["shift_mm"])
        )
    return {"seat_residual_n": residual, "rows": rows, "gains": gains}


def _classify(case: VehicleCase, speed: float) -> dict[str, object]:
    """Where inside the two profiles does the deepest slice sit?"""

    dynamics = VehicleDynamics(case)
    q0 = np.zeros(dynamics.dimension, dtype=float)
    velocity = np.zeros(dynamics.dimension, dtype=float)
    for body in dynamics.topology.bodies:
        try:
            spin = dynamics.topology.require(body.id, "spin")
        except (KeyError, TopologyError):
            continue
        velocity[spin] = speed / float(case.vehicle.nominal_wheel_radius_m)
    seated, _ = _seat(case, dynamics, q0, velocity)
    dynamics.evaluate(0.0, seated, velocity)

    wheel = case.wheels[0]
    rail = case.rails[0]
    x = case.run.x_start_m + float(np.mean(list(case.run.__dict__.get("axle_offsets_m", [0.0])) or [0.0]))
    sample = rail.profiles.sample(x, 1.0).profile
    rail_crown = float(sample.y_m[int(np.argmin(sample.z_m))])
    wheel_local = wheel.profile.y_m
    wheel_deepest_local = float(wheel_local[int(np.argmin(wheel.profile.z_m))])

    rail_id, entry = _contact(dynamics, seated)
    out: dict[str, object] = {
        "rail_id": rail_id,
        "rail_crown_mm": 1e3 * rail_crown,
        "wheel_offset_mm": 1e3 * wheel.lateral_offset_m,
        "wheel_deepest_local_mm": 1e3 * wheel_deepest_local,
        "tread_span_mm": [1e3 * float(wheel_local.min()), 1e3 * float(wheel_local.max())],
    }
    if entry is not None:
        geometry = entry.geometry
        local = geometry.lever_y_m - wheel.lateral_offset_m
        out.update(
            {
                "lever_y_mm": 1e3 * geometry.lever_y_m,
                "lever_minus_crown_mm": 1e3 * (geometry.lever_y_m - rail_crown),
                "lever_local_wheel_mm": 1e3 * local,
                "on_tread": bool(abs(local) <= 60.0e-3),
                "pinned_to_rail_crown": bool(abs(geometry.lever_y_m - rail_crown) < 2.0e-3),
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="case_A_plain.json")
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    parser.add_argument("--shifts-mm", type=float, nargs="+", default=[0.0, 1.0, 2.0, 4.0])
    parser.add_argument("--json", type=Path, default=None)
    options = parser.parse_args(argv)

    base = load_vehicle_case(case_dir() / options.case)
    speed = options.speed_kmh / 3.6
    shifts = tuple(value * 1e-3 for value in options.shifts_mm)

    print(f"case {options.case}  speed {options.speed_kmh:.1f} km/h")
    print(f"law defaults: patch_window {1e3 * base.contact.patch_window_m:.2f} mm, "
          f"strip_dy {1e3 * base.contact.strip_dy_m:.2f} mm")

    classification = _classify(base, speed)
    print("\n-- where the deepest slice sits (candidate 2) --")
    for key, value in classification.items():
        print(f"  {key:24s} {value}")

    report: dict[str, object] = {"classification": classification, "variants": {}}
    for label, overrides in VARIANTS:
        contact = dataclasses.replace(base.contact, **overrides) if overrides else base.contact
        variant_case = dataclasses.replace(base, contact=contact)
        result = sweep(variant_case, speed, shifts)
        report["variants"][label] = result
        print(f"\n-- {label} --")
        print(f"  seat residual {result['seat_residual_n']:.3e} N")
        print("  shift(mm)  lever_y(mm)  penetration(um)  normal(kN)")
        for row in result["rows"]:
            if not row.get("loaded"):
                print(f"  {row['shift_mm']:9.2f}  (no contact)")
                continue
            print(
                f"  {row['shift_mm']:9.2f}  {row['lever_y_mm']:11.3f}  "
                f"{row['penetration_um']:14.2f}  {row['normal_n'] / 1e3:10.2f}"
            )
        for key, value in result["gains"].items():
            print(f"  {key:28s} {value:+.4f}")

    theory = 1.0 / (2.0 * 0.300) * 1e3  # um per mm on a 300 mm crown
    print(f"\ntheory on a 300 mm crown: {theory:.1f} um/mm")
    report["theory_um_per_mm"] = theory

    if options.json is not None:
        options.json.parent.mkdir(parents=True, exist_ok=True)
        options.json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nreport -> {options.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
