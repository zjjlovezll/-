"""Does the point law hold the lateral state where the strip integral does not?

Round 14 measured a 37.77 mm sideways walk of the leading wheelset in 10 m on a straight,
symmetrically seated pair.  Round 15 measured ``d(sum Fy)/dy = 211.6 kN/mm`` and showed the contact
point barely follows the wheel -- both under ``normal_policy: strip_integral``, whose reported
``lever_y`` is the centroid of the whole overlap rather than the deepest strip.

``scripts/s76_normal_law.py`` then showed the pair seats under either law, the point law giving the
better balance (1.024x / 0.980x against 1.102x / 0.902x) but the *same* contact offset
(``lever_y -0.7365``, 16.7 mm inboard of the crown).  So that offset is conicity, not a strip
artefact: moving inboard raises the wheel radius faster than the rail crown falls, which is exactly
what a coned wheelset does when no lateral force is applied.

What has not been measured is the thing that actually blocked B047: the lateral drift over a run.
This script measures it under both laws with everything else identical.

Recompute::

    cd F:/ai道岔状态反演辨识/Velch
    PYTHONPATH=src python -X utf8 scripts/s76b_lateral_hold.py --duration 0.20
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, simulate_vehicle

EVEN_SHARE_N = 59_662.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-strip", default="../scratch/s73/case_straight_pair.json")
    parser.add_argument("--case-point", default="../scratch/s76/case_straight_pair_point.json")
    parser.add_argument("--duration", type=float, default=0.20)
    parser.add_argument("--out", default="../scratch/s76")
    options = parser.parse_args()

    out = Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    payload: dict[str, dict] = {}
    for label, path in (("strip", options.case_strip), ("point", options.case_point)):
        source = Path(path)
        if not source.exists():
            print(f"{label}: missing {source}; run scripts/s76_normal_law.py first")
            continue
        raw = json.loads(source.read_text(encoding="utf-8"))
        raw["run"]["x_start_m"] = 40.0
        raw["run"]["seat_x_start_m"] = 40.0
        raw["run"]["duration_s"] = options.duration
        raw["run"]["output_step_s"] = 0.005
        raw.pop("initial_state", None)
        target = out / f"case_{label}_run.json"
        target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

        case = load_vehicle_case(target)
        dynamics = VehicleDynamics(case)
        result = simulate_vehicle(case)
        status = result.summary.get("status") or result.summary.get("verdict")
        gates = result.summary.get("gates") or {}
        failed = [name for name, ok in gates.items() if not ok]
        times = np.asarray(result.times_s)
        positions = np.asarray(result.positions)
        print(
            f"{label:<6} frames {times.size:5d}  status {status}  gates "
            f"{sum(1 for ok in gates.values() if ok)}/{len(gates)}"
            + (f"  failing {failed}" if failed else "")
        )
        drift = {}
        for body in dynamics.topology.bodies:
            if "y" not in body.dof or not body.id.startswith("wheelset"):
                continue
            index = dynamics.topology.require(body.id, "y")
            column = positions[:, index]
            drift[body.id] = {
                "start_mm": float(column[0] * 1e3),
                "end_mm": float(column[-1] * 1e3),
                "max_abs_mm": float(np.max(np.abs(column)) * 1e3),
            }
        for name, values in drift.items():
            print(
                f"       {name:<10} y {values['start_mm']:+8.3f} -> {values['end_mm']:+8.3f} mm   "
                f"max |y| {values['max_abs_mm']:8.3f} mm"
            )
        payload[label] = {
            "status": status,
            "frames": int(times.size),
            "failed_gates": failed,
            "drift_mm": drift,
        }
    (out / "lateral_hold.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
