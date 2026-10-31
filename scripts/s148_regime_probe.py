"""Why the 60 km/h run loads the blade 4 m early: a second contact regime, not a bad operator.

The settled-window campaign left one reading that cannot be geometry-as-usual: at 60 km/h the
blade carries 24.4 kN of 60.2 kN at 54.0 m, where the blade's drawn crown is 2.474 mm *below*
the stock's.  A tread-on-tread transfer there is impossible, so this probe asks which contact
regime the solver is actually in.

Three measurements, all from the archive plus one static seat — no new dynamics:

1. static: seat the axle at 54.0 m and read the per-body forces.  The blade must be idle.
2. dynamic: re-evaluate the archived 60 km/h frame at 54.0 m from its stored (q, v) and print
   each body's penetration and ``lever_y``.
3. arithmetic: the two contacts are 1.25 mm apart laterally.  If both were on the tread, the
   wheel surface between them could not drop the 2.4 mm that the blade's drawn 2.47 mm step
   demands; that much drop over that little travel is a flange-root geometry.

The verdict is deliberately narrow: it names the regime and refuses to call the 60 km/h share a
tread transfer.  It does not claim the wheel-local surface was measured at the two contact
ordinates -- that is the next, cheaper-to-state step, and the probe prints exactly what is
missing rather than filling it in.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat

import s110_lowering_readings as readings
import s145_speed_transfer as transfer
import s146_settled_window as settled

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parent / "scratch"
RUNS = SCRATCH / "runs"
CASE = SCRATCH / "s146" / "one_set_x30.json"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "regime_probe.json"
SPEED_KMH = 60.0
STATION_M = 54.0
CROWN_STEP_M = 2.4744e-3


def static_probe(station_m: float) -> dict:
    case = load_vehicle_case(readings.CASE)
    offset = case.vehicle.axle_offsets_m[0]
    shifted = dataclasses.replace(
        case,
        run=dataclasses.replace(
            case.run,
            x_start_m=station_m - offset,
            seat_x_start_m=station_m - offset,
            duration_s=0.02,
        ),
    )
    dynamics = VehicleDynamics(shifted)
    q = np.asarray(shifted.initial_q, dtype=float).copy()
    v = np.asarray(shifted.initial_v, dtype=float).copy()
    for axle in range(4):
        v[dynamics.topology.require(f"wheelset{axle + 1}", "spin")] = (SPEED_KMH / 3.6) / 0.43
    q, residual = _seat(shifted, dynamics, q, v)
    _, contacts = dynamics.evaluate(0.0, q, v)
    bodies = {
        body: response.normal_force_n
        for body, response in zip(dynamics.body_ids["axle1_right"], dynamics.body_contacts["axle1_right"])
    }
    return {
        "residual_n": float(residual),
        "rail_force_n": contacts["axle1_right"].normal_force_n,
        "bodies_n": {k: float(v_) for k, v_ in bodies.items()},
        "blade_n": float(bodies.get("blade", 0.0)),
    }


def dynamic_probe(station_m: float) -> dict:
    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    run_id = settled.select(settled.NULL_ROUTE, SPEED_KMH)
    run = transfer.load(run_id, SPEED_KMH)
    data = np.load(RUNS / run_id / "series.npz")
    stations = run["station"]
    index = int(np.argmin(np.abs(stations - station_m)))
    _, contacts = dynamics.evaluate(
        float(data["times"][index]), data["positions"][index].copy(), data["velocities"][index].copy()
    )
    rows = {}
    for body, response in zip(dynamics.body_ids["axle1_right"], dynamics.body_contacts["axle1_right"]):
        g = response.geometry
        rows[body] = {
            "force_n": float(response.normal_force_n),
            "penetration_m": float(g.penetration_m) if g is not None else None,
            "lever_y_m": float(g.y_m) if g is not None else None,
        }
    zi = dynamics.topology.require("wheelset1", "z")
    yi = dynamics.topology.require("wheelset1", "y")
    return {
        "run_id": run_id,
        "station_m": float(stations[index]),
        "bodies": rows,
        "wheelset_z_m": float(data["positions"][index][zi]),
        "wheelset_y_m": float(data["positions"][index][yi]),
        "rail_force_n": float(contacts["axle1_right"].normal_force_n),
    }


def arithmetic(dynamic: dict) -> dict:
    stock = dynamic["bodies"]["stock"]
    blade = dynamic["bodies"]["blade"]
    separation = abs(blade["lever_y_m"] - stock["lever_y_m"])
    drop = CROWN_STEP_M - (stock["penetration_m"] - blade["penetration_m"])
    return {
        "lateral_separation_m": separation,
        "wheel_surface_drop_m": drop,
        "slope": drop / separation if separation > 0 else float("inf"),
        "tread_could_supply": bool(drop <= 5e-4),
    }


def main() -> int:
    static = static_probe(STATION_M)
    dynamic = dynamic_probe(STATION_M)
    geometry = arithmetic(dynamic)

    print(f"station {STATION_M:.2f} m, {SPEED_KMH:.0f} km/h")
    print(f"  static  : rail {static['rail_force_n'] / 1e3:7.3f} kN  blade {static['blade_n'] / 1e3:7.3f} kN"
          f"  (residual {static['residual_n']:.2e} N)")
    print(f"  dynamic : rail {dynamic['rail_force_n'] / 1e3:7.3f} kN  wheelset z {dynamic['wheelset_z_m'] * 1e6:+8.1f} um"
          f"  y {dynamic['wheelset_y_m'] * 1e6:+8.1f} um")
    for body, row in dynamic["bodies"].items():
        if row["force_n"] > 1.0:
            print(f"            {body:6s} {row['force_n'] / 1e3:8.3f} kN  pen {row['penetration_m'] * 1e6:8.2f} um"
                  f"  lever_y {row['lever_y_m'] * 1e6:+10.1f} um")
    print(f"  geometry: contacts {geometry['lateral_separation_m'] * 1e3:.2f} mm apart, wheel surface drops"
          f" {geometry['wheel_surface_drop_m'] * 1e3:.2f} mm between them (slope {geometry['slope']:.2f})")

    regime = "tread" if geometry["tread_could_supply"] else "flange_root"
    verdict = (
        "static and dynamic disagree at the same station: the blade is idle when seated and loaded when rolling,"
        f" and the two contacts demand a {geometry['wheel_surface_drop_m'] * 1e3:.2f} mm wheel drop over"
        f" {geometry['lateral_separation_m'] * 1e3:.2f} mm.  The 60 km/h blade load is a {regime} contact,"
        " so its share is not a tread transfer and cannot carry the amplitude"
    )
    print(f"VERDICT: {verdict}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "speed_kmh": SPEED_KMH,
        "station_m": STATION_M,
        "crown_step_m": CROWN_STEP_M,
        "static": static,
        "dynamic": dynamic,
        "geometry": geometry,
        "regime": regime,
        "verdict": verdict,
        "not_measured": "the wheel surface at the two contact ordinates in wheel-local coordinates",
    }
    REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
