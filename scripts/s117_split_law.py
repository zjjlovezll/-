"""Measure the split law itself: sigma as a function of the blade's height, with the real strip integral.

Round 253 fitted a contact model with one stiffness per body and concluded that something it could not name
was compressing the amplitude.  Round 254's sink probe then removed the obvious candidate: the rail node is
shared, all eight rails sink by the same 1.2027 mm, so the sink is common mode and cancels from the gap.

That leaves the law inside the contact.  This script measures it rather than assuming it: lift or lower the
whole blade body by a known offset, re-seat, and read the split the real solver produces.  The result is the
sigma(u) curve that any estimator has to use, and it can be compared directly with the one-stiffness model.

Purpose is measurement: no estimator is fitted to gate here, and nothing is tuned to pass anything.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics, _seat  # noqa: E402

CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s117"
RAIL = "axle1_right"
OFFSETS_UM = (-250.0, -150.0, -80.0, -40.0, -20.0, -10.0, -5.0, 0.0,
              5.0, 10.0, 20.0, 40.0, 80.0, 150.0, 250.0)
STATION_M = 58.0
# The blade body only exists from 50.578 m, so the probe has to sit inside its range: seat the front
# axle at 58.0 m (x_start 48.0 + the 10 m front-axle offset) rather than at the canonical 50.0 m.
X_START_M = STATION_M - 10.0


def _shifted_blade(base: dict, delta_m: float) -> dict:
    """A copy of the case whose blade body sits ``delta_m`` higher (positive = raised)."""
    case = json.loads(json.dumps(base))
    case["run"]["x_start_m"] = X_START_M
    if "seat_x_start_m" in case["run"]:
        case["run"]["seat_x_start_m"] = X_START_M
    for template in case["rail_templates"]:
        for body in template.get("bodies", []):
            if body.get("id") != "blade":
                continue
            for station in body["stations"]:
                station["profile"]["z_offset_m"] = (
                    float(station["profile"].get("z_offset_m", 0.0)) + delta_m)
    return case


def _split_at_the_front_axle(case_dict: dict) -> dict:
    path = OUT / "variant.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(case_dict), encoding="utf-8")
    case = load_vehicle_case(path)
    dynamics = VehicleDynamics(case)
    q = np.asarray(case.initial_q, dtype=float)
    v = np.asarray(case.initial_v, dtype=float)
    v[dynamics.topology.require("wheelset1", "spin")] = 80.0 / 3.6 / 0.43
    q, residual = _seat(case, dynamics, q, v)
    _, contacts = dynamics.evaluate(0.0, q, v)
    bodies = dict(zip(dynamics.body_ids[RAIL], dynamics.body_contacts[RAIL]))
    forces = {body_id: (float(response.normal_force_n) if response.active
                        and response.geometry is not None else 0.0)
              for body_id, response in bodies.items()}
    stock, blade = forces.get("stock", 0.0), forces.get("blade", 0.0)
    merged = contacts[RAIL]
    return {"residual_n": residual, "stock_n": stock, "blade_n": blade,
            "total_n": stock + blade,
            "sigma": blade / (stock + blade) if stock + blade > 0 else float("nan"),
            "half_width_m": float(merged.geometry.half_width_m) if merged.geometry is not None else float("nan"),
            "stock_active": stock > 0.0, "blade_active": blade > 0.0,
            "lever_y_m": float(merged.geometry.y_m) if merged.geometry is not None else float("nan")}


def main() -> int:
    base = json.loads(CASE.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    print(f"{'delta (um)':>11s} {'stock (kN)':>11s} {'blade (kN)':>11s} {'total (kN)':>11s} "
          f"{'sigma':>7s} {'halfwidth (mm)':>15s} {'lever_y (mm)':>13s} {'residual (N)':>13s}")
    for offset in OFFSETS_UM:
        # Positive offset in the table means "raise the blade", i.e. a negative delta in height.
        result = _split_at_the_front_axle(_shifted_blade(base, -offset * 1e-6))
        rows.append({"offset_um": offset, **result})
        print(f"{offset:11.1f} {result['stock_n'] / 1e3:11.2f} {result['blade_n'] / 1e3:11.2f} "
              f"{result['total_n'] / 1e3:11.2f} {result['sigma']:7.4f} "
              f"{result['half_width_m'] * 1e3:15.3f} {result['lever_y_m'] * 1e3:13.3f} "
              f"{result['residual_n']:13.2e}")

    finite = [row for row in rows if np.isfinite(row["sigma"])]
    span = (min(row["sigma"] for row in finite), max(row["sigma"] for row in finite))
    print()
    print(f"sigma spans {span[0]:.4f} .. {span[1]:.4f} over +-250 um of blade height")
    print(f"frames where the stock carries nothing: "
          f"{sum(1 for row in finite if not row['stock_active'])}/{len(finite)}")
    # Where does the split cross one half?  That is the transfer point every estimator keys on.
    crossings = []
    for low, high in zip(finite, finite[1:]):
        if low["sigma"] < 0.5 <= high["sigma"] or high["sigma"] < 0.5 <= low["sigma"]:
            t = (0.5 - low["sigma"]) / (high["sigma"] - low["sigma"])
            crossings.append(low["offset_um"] + t * (high["offset_um"] - low["offset_um"]))
    print(f"sigma = 0.5 at offset(s) {['%.1f um' % value for value in crossings]}")

    (OUT / "split_law.json").write_text(json.dumps(
        {"rail": RAIL, "station_m": STATION_M, "offsets_um": list(OFFSETS_UM),
         "rows": rows, "crossings_um": crossings}, indent=1) + chr(10), encoding="utf-8")
    print(f"report -> {OUT / 'split_law.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
