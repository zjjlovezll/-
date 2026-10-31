"""How much lateral room does the straight-side wheel have at the 60 km/h failure station?

Round 292–294 found that the corrected 60 km/h case (B052) dies within 0.06 s with
    graph slope limit at axle2_left/left:main, x=53.5 m
while the identical geometry at 80 km/h completes.  The seat at that start is clean
(2.900e-08 N, 60.153 kN per contact, 62.84 um), so the difference is a dynamic state
difference -- and the cheapest quantity that can explain a 0.06 s trip is the **lateral
margin**: how far the wheel can move before a patch on the straight rail becomes steep
enough for the guard.

This probe seats once at the failing start, then moves `wheelset2.y` (the axle that
tripped) in small steps and evaluates -- it never integrates.  It reports, per rail, the
steepest normal slope the contact search returned, the penetration, and whether that
slope would trip `maximum_abs_contact_slope` (1.0).

Deliberately *not* reported: any amplitude, any speed-transfer conclusion.  A margin is
not a defect until the failing trajectory is shown to reach it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from velch.solver import SimulationFailure  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics, _seat  # noqa: E402

CASE = Path(r"F:/ai道岔状态反演辨识/scratch/s146/one_set_x46.json")
SPEED_KMH = 60.0
AXLE = 2
STEPS_UM = (-50.0, -30.0, -20.0, -10.0, -5.0, 0.0, 5.0, 10.0, 20.0, 30.0, 50.0)
GUARD = 1.0
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "lateral_margin.json"


def _seated():
    case = load_vehicle_case(CASE)
    dyn = VehicleDynamics(case)
    q = np.asarray(case.initial_q, dtype=float)
    v = np.asarray(case.initial_v, dtype=float)
    for axle in (1, 2, 3, 4):
        v[dyn.topology.require(f"wheelset{axle}", "spin")] = SPEED_KMH / 3.6 / 0.43
    q, residual = _seat(case, dyn, q, v)
    return case, dyn, q, v, float(residual)


def _slopes(dyn, q, v):
    """Per rail: steepest |normal slope| among the live patches, penetration, lever_y."""
    out = {}
    _, contacts = dyn.evaluate(0.0, q, v)
    bodies = dyn.body_contacts
    for rail_id, total in contacts.items():
        parts = [r for r in bodies.get(rail_id, ()) if r.active and r.geometry is not None]
        if not parts:
            out[rail_id] = None
            continue
        steepest = max(
            (abs(float(p.geometry.normal_y) / float(p.geometry.normal_z)), p) for p in parts
        )
        slope, worst = steepest
        out[rail_id] = {
            "slope": slope,
            "penetration_um": float(worst.geometry.penetration_m) * 1e6,
            "lever_y_mm": float(worst.geometry.lever_y_m) * 1e3,
            "normal_force_kn": float(total.normal_force_n) / 1e3,
            "bodies": len(parts),
            "trips": slope > GUARD,
        }
    return out


def main() -> int:
    case, dyn, q, v, residual = _seated()
    y_index = dyn.topology.require(f"wheelset{AXLE}", "y")
    print(f"case {CASE.name}  speed {SPEED_KMH} km/h  seat residual {residual:.3e} N")
    print(f"axle{AXLE} left station at t=0: "
          f"{case.run.x_start_m + case.vehicle.axle_offsets_m[0] - 2.5:.1f} m (front axle starts at "
          f"{case.run.x_start_m + case.vehicle.axle_offsets_m[0]:.1f} m)")

    rows = []
    failure = None
    for step in STEPS_UM:
        state = q.copy()
        state[y_index] = q[y_index] + step * 1e-6
        try:
            slopes = _slopes(dyn, state, v)
        except SimulationFailure as exc:  # the guard itself fired
            failure = {"dy_um": step, "error": str(exc).splitlines()[0]}
            print(f"  dy {step:+7.1f} um -> SimulationFailure: {failure['error'][:90]}")
            rows.append({"dy_um": step, "failure": failure["error"]})
            continue
        left = slopes.get(f"axle{AXLE}_left")
        right = slopes.get(f"axle{AXLE}_right")
        rows.append({"dy_um": step, "left": left, "right": right})
        for side, entry in (("left", left), ("right", right)):
            if entry is None:
                print(f"  dy {step:+7.1f} um  {side:5s} no contact")
                continue
            flag = "  <-- would trip" if entry["trips"] else ""
            print(f"  dy {step:+7.1f} um  {side:5s} slope {entry['slope']:6.3f} "
                  f"pen {entry['penetration_um']:7.2f} um  lever_y {entry['lever_y_mm']:9.3f} mm  "
                  f"N {entry['normal_force_kn']:7.3f} kN  patches {entry['bodies']}{flag}")

    tripping = [r["dy_um"] for r in rows if isinstance(r.get("left"), dict) and r["left"]["trips"]]
    first = min(tripping) if tripping else None
    print()
    print(f"[MARGIN] first dy that trips the guard on axle{AXLE}_left: "
          f"{first if first is not None else 'none within the sweep'} um")
    if failure is not None:
        print(f"[MARGIN] the sweep also raised SimulationFailure directly at dy = {failure['dy_um']:+.1f} um")
    print("[MARGIN] a margin is not a defect until the failing trajectory is shown to reach it")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    import json

    REPORT.write_text(
        json.dumps(
            {
                "case": str(CASE),
                "speed_kmh": SPEED_KMH,
                "axle": AXLE,
                "seat_residual_n": residual,
                "steps_um": list(STEPS_UM),
                "rows": rows,
                "first_tripping_dy_um": first,
                "guard": GUARD,
                "note": "static lateral margin; not an amplitude and not a speed-transfer result",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
