"""Hold the wheelset where the archive says it was, and see whether the blade takes 5 % there.

Round 308 read the three archived runs and found that at 58.150 m the 60 km/h front wheelset sits 3.096 mm
away from where the 80 km/h one sits, drifting inboard at about 1 mm per metre.  That is the right size to
carry the 0.145 m offset between the static 5 % reference (58.145 m) and the measured 60 km/h station
(58.000 m), but the sign could not be settled: the pre-registered predicate demanded a displacement in one
direction and the measurement gave the other, and the only sign convention on record (round 74's
``d(lever_y)/dq[y] = -1``) was measured on a different state and never re-checked here.

So this probe measures the thing that does not need a convention.  It imposes the lateral displacement on the
seated state and reads the share:

    H9  (convention): the contact's absolute y moves against the imposed q[y], i.e. d(lever_y)/dq[y] < 0,
        with a magnitude in [0.5, 1.5] -- round 74 measured -1.0000 on a rigid straight case.

    H10 (mechanism, convention free): at the measured displacement dy = -3.096 mm the blade's share at
        58.150 m rises from about 0 to [0.03, 0.08], i.e. to the 5 % that the 60 km/h run reached 0.145 m
        earlier than the static reference predicts.

    falsifier: share(dy = -3.096 mm) < 0.02.  Then the lateral registration does not carry the 0.145 m and
    the offset goes back to unexplained, with the rail bodies' lateral compliance as the next candidate.

The seat is run with ``run.seat_lateral = False`` so the lateral coordinate is an imposed input rather than a
solved unknown; after seating vertically the imposed displacement is re-applied and the vertical rows are
re-solved with it held, so the share is not a transient of an inconsistent state.  The imposed value is
asserted back out of the state before anything is read.

Purpose is measurement: one station, one speed, five displacements, nothing fitted, no gate judged.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics, _seat  # noqa: E402

CASE = ROOT.parent / "scratch" / "s146" / "one_set_x46.json"
SCRATCH = ROOT.parent / "scratch" / "s161"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "lateral_split.json"
RAIL = "axle1_right"
STATION_M = 58.150
AXLE_OFFSET_M = 10.0
SPEED_KMH = 60.0                       # the speed whose offset has to be explained
ROLL_RADIUS_M = 0.43
DISPLACEMENTS_MM = (-3.096, -3.0, -1.5, 0.0, 1.5, 3.0)
MEASURED_DISPLACEMENT_MM = -3.096
SLOPE_DISPLACEMENTS_MM = (-3.0, -1.5, 0.0, 1.5, 3.0)
SHARE_WINDOW = (0.03, 0.08)
SHARE_FLOOR = 0.02
LEVER_SLOPE_WINDOW = (0.5, 1.5)


def seat_with_displacement(displacement_m: float) -> dict:
    """Seat at ``STATION_M`` with the front wheelset's lateral coordinate held at ``displacement_m``."""
    SCRATCH.mkdir(parents=True, exist_ok=True)
    base = json.loads(CASE.read_text(encoding="utf-8"))
    base["run"]["x_start_m"] = STATION_M - AXLE_OFFSET_M
    if "seat_x_start_m" in base["run"]:
        base["run"]["seat_x_start_m"] = STATION_M - AXLE_OFFSET_M
    base["run"]["seat_lateral"] = False          # y is an input here, not an unknown
    variant = SCRATCH / f"lateral_{displacement_m * 1e3:+07.3f}mm.json"
    variant.write_text(json.dumps(base), encoding="utf-8")

    case = load_vehicle_case(variant)
    dynamics = VehicleDynamics(case)
    q = np.asarray(case.initial_q, dtype=float)
    v = np.asarray(case.initial_v, dtype=float)
    v[dynamics.topology.require("wheelset1", "spin")] = SPEED_KMH / 3.6 / ROLL_RADIUS_M
    q, residual = _seat(case, dynamics, q, v)

    y_index = dynamics.topology.require("wheelset1", "y")
    q[y_index] = displacement_m
    q, residual = _seat(case, dynamics, q, v)
    assert abs(q[y_index] - displacement_m) < 1e-12, "the seat moved the imposed lateral coordinate"
    _, _contacts = dynamics.evaluate(0.0, q, v)

    rows = {}
    for body_id, response in zip(dynamics.body_ids[RAIL], dynamics.body_contacts[RAIL]):
        geometry = response.geometry
        rows[str(body_id).split(":")[-1]] = {
            "force_n": float(response.normal_force_n) if (response.active and geometry is not None) else 0.0,
            "penetration_m": float(geometry.penetration_m) if geometry is not None else 0.0,
            "y_m": float(geometry.y_m) if geometry is not None else float("nan"),
            "active": bool(response.active and geometry is not None),
        }
    stock, blade = rows.get("stock", {}), rows.get("blade", {})
    total = stock.get("force_n", 0.0) + blade.get("force_n", 0.0)
    return {
        "displacement_m": float(displacement_m),
        "residual_n": float(residual),
        "stock_force_n": stock.get("force_n", 0.0),
        "blade_force_n": blade.get("force_n", 0.0),
        "stock_penetration_m": stock.get("penetration_m", 0.0),
        "blade_penetration_m": blade.get("penetration_m", 0.0),
        "stock_y_m": stock.get("y_m", float("nan")),
        "blade_y_m": blade.get("y_m", float("nan")),
        "share": blade.get("force_n", 0.0) / total if total > 0 else float("nan"),
        "total_n": total,
    }


def main(argv: list | None = None) -> int:
    rows = [seat_with_displacement(displacement * 1e-3) for displacement in DISPLACEMENTS_MM]

    print(f"station {STATION_M:.3f} m, {SPEED_KMH:.0f} km/h, front wheelset lateral displacement imposed")
    print("      dy mm    share   stock kN   blade kN   pen stock   pen blade   stock y mm   blade y mm")
    for row in rows:
        print(f"{1e3 * row['displacement_m']:+11.3f}  {100 * row['share']:6.2f}%"
              f"  {row['stock_force_n'] / 1e3:9.3f}  {row['blade_force_n'] / 1e3:9.3f}"
              f"  {1e6 * row['stock_penetration_m']:10.2f}  {1e6 * row['blade_penetration_m']:10.2f}"
              f"  {1e3 * row['stock_y_m']:12.4f}  {1e3 * row['blade_y_m']:12.4f}")

    slope_rows = [row for row in rows if any(abs(1e3 * row["displacement_m"] - d) < 1e-9 for d in SLOPE_DISPLACEMENTS_MM)]
    dy = np.array([row["displacement_m"] for row in slope_rows])
    shares = np.array([row["share"] for row in slope_rows])
    share_slope = float(np.polyfit(dy, shares, 1)[0]) if dy.size > 2 else float("nan")

    lever_rows = [row for row in slope_rows if np.isfinite(row["stock_y_m"])]
    lever_slope = float("nan")
    if len(lever_rows) > 2:
        lever_slope = float(np.polyfit([row["displacement_m"] for row in lever_rows],
                                       [row["stock_y_m"] for row in lever_rows], 1)[0])

    target = next(row for row in rows if abs(1e3 * row["displacement_m"] - MEASURED_DISPLACEMENT_MM) < 1e-9)
    share_at_measured = float(target["share"])
    h10 = SHARE_WINDOW[0] <= share_at_measured <= SHARE_WINDOW[1]
    h9 = np.isfinite(lever_slope) and -LEVER_SLOPE_WINDOW[1] <= lever_slope <= -LEVER_SLOPE_WINDOW[0]

    print()
    print(f"d(share)/d(dy)   {1e3 * share_slope:+.4f} per mm     ({len(slope_rows)} displacements)")
    print(f"d(lever_y)/dq[y] {lever_slope:+.4f}                (round 74 measured -1.0000)")
    print(f"share at dy = {MEASURED_DISPLACEMENT_MM:+.3f} mm   {100 * share_at_measured:.2f} %"
          f"   window {SHARE_WINDOW[0]:.0%}-{SHARE_WINDOW[1]:.0%}   -> H10 {'CONFIRMED' if h10 else 'REFUTED'}")
    print(f"H9 (the contact moves against the imposed coordinate): {'CONFIRMED' if h9 else 'REFUTED'}")
    if not h10:
        print("  the lateral registration does not carry the 0.145 m offset; next candidate is the rail bodies")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "constants": {"station_m": STATION_M, "speed_kmh": SPEED_KMH, "axle_offset_m": AXLE_OFFSET_M,
                      "displacements_mm": list(DISPLACEMENTS_MM),
                      "measured_displacement_mm": MEASURED_DISPLACEMENT_MM,
                      "share_window": list(SHARE_WINDOW), "share_floor": SHARE_FLOOR,
                      "lever_slope_window": list(LEVER_SLOPE_WINDOW)},
        "rows": rows,
        "slopes": {"share_per_m": share_slope, "lever_y_per_displacement": lever_slope},
        "share_at_measured_displacement": share_at_measured,
        "H9_convention_confirmed": bool(h9),
        "H10_mechanism_confirmed": bool(h10),
    }, indent=1, sort_keys=True), encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0 if h10 else 1


if __name__ == "__main__":
    raise SystemExit(main())
