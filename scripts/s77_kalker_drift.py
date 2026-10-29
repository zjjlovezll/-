"""Is the leading wheelset's sideways walk kinematic hunting, and does Kalker-scale creep damp it?

Measured (round 16, `scripts/s76b_lateral_hold.py`, straight pair, seat at 40 m, 80 km/h, 0.20 s):

    law     wheelset1 y     wheelset2 y
    strip   -5.295 mm       -0.913 mm
    point   -5.261 mm       -0.871 mm

so the walk is **not** an artefact of the strip integral, and switching to the point law does not
change it.  A wheelset drifting at a steady rate on a straight, symmetric pair is the signature of
kinematic hunting: with a coned tread the wheelset has a Klingel wavelength

    lambda = 2*pi*sqrt(r0*b/(2*tan(delta)))

which for r0 = 0.43 m, b = 0.7465 m and tan(delta) = 1/40 gives about 11.3 m, i.e. 0.51 s at
22.22 m/s -- so 0.20 s is roughly a quarter period and a few millimetres is the expected amplitude.
Whether it *grows* or stays bounded is decided by the creep coefficients: the frozen pair
(f11 = 1.0e6, f22 = 5.0e5 N) is 3.5x and 5x below Kalker's values for a 60 kN wheel, so the
damping term that would bound the oscillation is small.

This script asks that one question: with Kalker-scale creep on an otherwise identical point-law
case, does the drift stay bounded?

Recompute::

    cd F:/ai道岔状态反演辨识/Velch
    PYTHONPATH=src python -X utf8 scripts/s77_kalker_drift.py --duration 0.60
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, simulate_vehicle

HERE = Path(__file__).resolve().parents[1]
KALKER_X_N = 3.5e6
KALKER_LATERAL_N = 2.5e6


def _point_law(raw: dict) -> dict:
    contact = dict(raw.get("contact") or {})
    for key in ("normal_policy", "strip_dy_m", "stiffness_policy"):
        contact.pop(key, None)
    contact["normal_model"] = "hertz_effective_radius"
    contact["effective_radius_m"] = 0.02
    raw["contact"] = contact
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="../scratch/s76/case_straight_pair_point.json")
    parser.add_argument("--duration", type=float, default=0.60)
    parser.add_argument("--start-at", type=float, default=40.0)
    parser.add_argument("--out", default="../scratch/s77")
    options = parser.parse_args()

    out = Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    source = Path(options.case)
    if not source.exists():
        raise SystemExit(f"missing {source}; run scripts/s76_normal_law.py first")

    payload: dict[str, dict] = {}
    for label, kalker in (("frozen_creep", False), ("kalker_creep", True)):
        raw = _point_law(json.loads(source.read_text(encoding="utf-8")))
        raw.setdefault("contact", {})
        if kalker:
            raw["contact"]["creep_stiffness_x_n"] = KALKER_X_N
            raw["contact"]["creep_stiffness_lateral_n"] = KALKER_LATERAL_N
        raw.setdefault("run", {})
        raw["run"]["x_start_m"] = options.start_at
        raw["run"]["seat_x_start_m"] = options.start_at
        raw["run"]["duration_s"] = options.duration
        raw["run"]["output_step_s"] = 0.005
        raw.pop("initial_state", None)
        raw["case_id"] = f"straight_pair_{label}"
        target = out / f"case_{label}.json"
        target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

        case = load_vehicle_case(target)
        dynamics = VehicleDynamics(case)
        try:
            result = simulate_vehicle(case)
        except Exception as error:  # noqa: BLE001 - the failure mode is a result here
            print(f"{label:<13} run FAILED: {type(error).__name__}: {error}")
            payload[label] = {"status": "failed", "error": f"{type(error).__name__}: {error}"}
            continue
        gates = result.summary.get("gates") or {}
        positions = np.asarray(result.positions)
        times = np.asarray(result.times_s)
        drift = {}
        for body in dynamics.topology.bodies:
            if "y" not in body.dof or not body.id.startswith("wheelset"):
                continue
            column = positions[:, dynamics.topology.require(body.id, "y")]
            drift[body.id] = {
                "end_mm": float(column[-1] * 1e3),
                "max_abs_mm": float(np.max(np.abs(column)) * 1e3),
                "trend_mm_per_s": float((column[-1] - column[0]) / max(times[-1], 1e-9) * 1e3),
            }
        print(
            f"{label:<13} frames {times.size:4d}  t_end {times[-1]:.3f} s  gates "
            f"{sum(1 for ok in gates.values() if ok)}/{len(gates)}"
        )
        for name, values in drift.items():
            print(
                f"       {name:<10} y_end {values['end_mm']:+8.3f} mm  max|y| {values['max_abs_mm']:8.3f} mm  "
                f"trend {values['trend_mm_per_s']:+9.3f} mm/s"
            )
        payload[label] = {"gates": gates, "frames": int(times.size), "drift": drift}

    (out / "kalker_drift.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
