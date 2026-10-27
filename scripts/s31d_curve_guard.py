"""Which contact does the geometry-route slope guard reject, and with what vehicle state?

The geometry route now seats exactly (eight rails at 0.988..1.013x the even share) and then dies
with `graph slope limit at axle1_left/left:main, x=41.2329879 m`, i.e. after 1.23 m of travel.  A
1.23 m advance grows the design line's offset by only 11 mm, so the guard is not reporting a large
lateral excursion; it is reporting that the *contact point* moved onto a steep part of the section.

This probe records, for every contact geometry the run evaluates, the steepest one together with
the vehicle state that produced it, and prints the trip frame next to the first frame.

Run:  python -X utf8 scripts/s31d_curve_guard.py [--duration 0.06]
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

import velch.vehicle_solver as vs
from velch.solver import SimulationFailure
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, simulate_vehicle

BASE_CASE = Path(r"F:\velch_data\validation\crh380a_m\case_A_final_law.json")
OUT = Path(r"F:\ai道岔状态反演辨识\scratch\s31d")
SPEED_KMH = 80.0
RADIUS_M = 1100.0
X_START_M = 30.0


def build(radius_m: float, speed_kmh: float, duration_s: float, x_start_m: float) -> Path:
    """``case_A_final_law`` (one source, 1.493 m gauge) moved onto a geometry-route curve."""

    raw = json.loads(BASE_CASE.read_text(encoding="utf-8"))
    raw.pop("initial_state", None)
    raw["case_id"] = f"case_curve_r{radius_m:.0f}_{speed_kmh:.0f}_geometry"
    raw["vehicle"]["travel_speed_m_s"] = speed_kmh / 3.6
    raw["run"].update({
        "x_start_m": x_start_m,
        "seat_x_start_m": x_start_m,
        "duration_s": duration_s,
        "output_step_s": 1.0e-2,
        "method": "BDF",
        "jacobian": "analytic",
        "curve_radius_m": radius_m,
        "curve_geometry": True,
        "align_to_track": True,
    })
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "case_curve_geometry.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=0.06)
    options = parser.parse_args()

    case = load_vehicle_case(build(RADIUS_M, SPEED_KMH, options.duration, X_START_M))
    dynamics = VehicleDynamics(case)
    original_evaluate = vs.VehicleDynamics.evaluate
    original_contact = vs.find_graph_contact
    state: dict[str, object] = {"t": 0.0, "q": None, "v": None}
    call_index = [0]
    first: list[dict[str, object]] = []
    best: dict[str, object] = {"slope": 0.0}

    def evaluate(self, t_s, q, v):  # type: ignore[no-untyped-def]
        state["t"] = float(t_s)
        state["q"] = np.array(q, dtype=float, copy=True)
        state["v"] = np.array(v, dtype=float, copy=True)
        return original_evaluate(self, t_s, q, v)

    def traced(profile, sample, **kwargs):  # type: ignore[no-untyped-def]
        geometry = original_contact(profile, sample, **kwargs)
        if geometry is None:
            return geometry
        call_index[0] += 1
        slope = abs(float(geometry.normal_y) / float(geometry.normal_z))
        row = {
            "call": call_index[0],
            "t": float(state["t"]),
            "profile": str(profile.source)[-42:],
            "wheel_y_m": float(kwargs["wheel_y_m"]),
            "lateral_offset_m": float(kwargs["wheel_lateral_offset_m"]),
            "rail_y_m": float(kwargs["rail_y_m"]),
            "rail_z_m": float(kwargs["rail_z_m"]),
            "rail_band": (float(np.min(sample.profile.y_m)), float(np.max(sample.profile.y_m))),
            "y_m": float(geometry.y_m),
            "penetration_um": float(geometry.penetration_m) * 1e6,
            "n_y": float(geometry.normal_y),
            "n_z": float(geometry.normal_z),
            "slope": slope,
        }
        if len(first) < 4:
            first.append(row)
        if slope > float(best["slope"]):
            best.clear()
            best.update(row)
            best["q"] = None if state["q"] is None else np.array(state["q"], dtype=float, copy=True)
            best["v"] = None if state["v"] is None else np.array(state["v"], dtype=float, copy=True)
        return geometry

    vs.VehicleDynamics.evaluate = evaluate  # type: ignore[assignment]
    vs.find_graph_contact = traced  # type: ignore[assignment]
    failure = None
    try:
        result = simulate_vehicle(case)
        print("run", result.summary["result_status"], "frames", len(result.times_s))
    except SimulationFailure as error:
        failure = str(error)
        print("FAILED", failure)
    finally:
        vs.VehicleDynamics.evaluate = original_evaluate  # type: ignore[assignment]
        vs.find_graph_contact = original_contact  # type: ignore[assignment]

    topology = dynamics.topology
    rows = []
    for body in topology.wheelsets():
        row = {"wheelset": body.id}
        for axis in ("y", "z", "roll", "yaw"):
            if axis in body.dof:
                row[axis] = float(best["q"][topology.require(body.id, axis)]) if best.get("q") is not None else float("nan")
                row[axis + "_dot"] = (float(best["v"][topology.require(body.id, axis)])
                                      if best.get("v") is not None else float("nan"))
        rows.append(row)

    print(f"\nsteepest contact: call {best['call']} of {call_index[0]}  t {float(best['t']):.4f} s")
    for key in ("profile", "wheel_y_m", "lateral_offset_m", "rail_y_m", "rail_z_m", "rail_band",
                "y_m", "penetration_um", "n_y", "n_z", "slope"):
        print(f"  {key:16s} {best[key]}")
    print("\nfirst contacts:")
    for row in first:
        print(f"  call {row['call']:4d} t {row['t']:.4f} wheel_y {row['wheel_y_m']:+.5f} "
              f"offset {row['lateral_offset_m']:+.5f} rail_y {row['rail_y_m']:+.5f} "
              f"y {row['y_m']:+.5f} pen {row['penetration_um']:+8.2f} um "
              f"slope {row['slope']:.4f}")
    print("\nwheelset state at the steepest contact:")
    for row in rows:
        print("  " + "  ".join(f"{key}={value:+.6f}" if isinstance(value, float) else f"{value}"
                               for key, value in row.items()))

    report = {"failure": failure, "steepest": {k: v for k, v in best.items() if k not in {"q", "v"}},
              "first": first, "wheelsets": rows,
              "calls": call_index[0],
              "demand": {"centripetal_n": 48654.0 * (SPEED_KMH / 3.6) ** 2 / RADIUS_M,
                         "share_n": 477444.6 / 8}}
    (OUT / "guard.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print(f"\nwrote {OUT / 'guard.json'}")
    print(f"centripetal demand {report['demand']['centripetal_n']:.1f} N vs even share "
          f"{report['demand']['share_n']:.1f} N per wheel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
