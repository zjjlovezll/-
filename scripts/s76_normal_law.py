"""Compare the two normal laws on the same straight pair: strip integral vs the frozen point law.

Why this exists
---------------
B047 was measured entirely on a case that inherits ``normal_policy: strip_integral`` with
``stiffness_policy: local_circular`` from the diverging turnout case.  In that law

    ``force = 0.25 * pi * E* * sum(depth) * step``       (contact_search.py, find_strip_contact)
    ``y_c   = sum(grid * depth) / sum(depth)``           <-- the REPORTED lever_y

so the reported contact point is the **centroid of the whole wheel/rail overlap**, not the deepest
strip, and the force is the integral over that whole band.  Two measured consequences follow and
neither is a tolerance question:

* the contact point does not follow the wheel: 36 mm of wheel travel moves ``lever_y`` 6 mm;
* ``d(sum Fy)/dy = 211.6 kN/mm`` at the shipped registration.

The frozen anchor (59 680.5769 N / 65.47 um) was calibrated with the **point** law
(``hertz_effective_radius``, ``effective_radius_m = 0.02``, no strip integral).  So the straight
two-body case has been running a different normal model from the anchor it is supposed to be
comparable to.  This script asks one question: does the pair seat and hold its lateral state under
the same law as the anchor?

Recompute::

    cd F:/ai道岔状态反演辨识/Velch
    PYTHONPATH=src python -X utf8 scripts/s76_normal_law.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat

HERE = Path(__file__).resolve().parents[1]
EVEN_SHARE_N = 59_662.0
SPEED_KMH = 80.0


def _strip(case_path: Path) -> dict:
    """Drop the strip integral so the point law of the frozen anchor is used."""
    raw = json.loads(case_path.read_text(encoding="utf-8"))
    contact = dict(raw.get("contact") or {})
    for key in ("normal_policy", "strip_dy_m", "stiffness_policy"):
        contact.pop(key, None)
    contact["normal_model"] = "hertz_effective_radius"
    contact["effective_radius_m"] = 0.02
    raw["contact"] = contact
    raw["case_id"] = f"{raw['case_id']}_pointlaw"
    raw["purpose_detail"] = (
        str(raw.get("purpose_detail", ""))
        + " | normal law = hertz_effective_radius, effective_radius 0.02 m (same as the frozen anchor)"
    )
    return raw


def _report(label: str, case_path: Path, seat_at: float, out: Path) -> dict:
    raw = json.loads(case_path.read_text(encoding="utf-8"))
    run = raw.setdefault("run", {})
    run["x_start_m"] = float(seat_at)
    run["seat_x_start_m"] = float(seat_at)
    run["duration_s"] = 0.001
    run["output_step_s"] = 0.001
    raw.pop("initial_state", None)
    tmp = out / f"case_{label}_seat{seat_at:.0f}.json"
    tmp.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    case = load_vehicle_case(tmp)
    dynamics = VehicleDynamics(case)
    speed = SPEED_KMH / 3.6
    velocity = np.zeros(dynamics.dimension)
    for body in dynamics.topology.bodies:
        if "spin" in body.dof:
            velocity[dynamics.topology.require(body.id, "spin")] = speed / case.vehicle.nominal_wheel_radius_m
    q = np.zeros(dynamics.dimension)
    try:
        q, residual = _seat(case, dynamics, q, velocity)
    except Exception as error:  # noqa: BLE001 - the failure mode is the measurement here
        print(f"{label:<6} seat at {seat_at:>6.1f} m FAILED: {type(error).__name__}: {error}")
        return {"label": label, "seated": False, "error": f"{type(error).__name__}: {error}"}
    dynamics.placement_enabled = True
    _force, contacts = dynamics.evaluate(0.0, q, velocity)
    rows = []
    for rail in case.rails:
        response = contacts.get(rail.id)
        if response is None or not getattr(response, "active", False):
            continue
        geometry = response.geometry
        rows.append(
            {
                "rail": rail.id,
                "n_kn": response.normal_force_n / 1e3,
                "ratio": response.normal_force_n / EVEN_SHARE_N,
                "pen_um": geometry.penetration_m * 1e6,
                "lever_y": geometry.lever_y_m,
                "fy_kn": response.wheel_force_y_n / 1e3,
            }
        )
    sum_n = sum(row["n_kn"] for row in rows)
    sum_fy = sum(row["fy_kn"] for row in rows)
    print(
        f"{label:<6} seat at {seat_at:>6.1f} m  residual {residual:.3e} N  patches {len(rows)}  "
        f"sum N {sum_n:.1f} kN  sum Fy {sum_fy:+.1f} kN"
    )
    for row in rows:
        print(
            f"       {row['rail']:<12} N {row['n_kn']:7.1f} kN  {row['ratio']:.3f}x  "
            f"pen {row['pen_um']:7.2f} um  lever_y {row['lever_y']:+.5f}  Fy {row['fy_kn']:+7.1f} kN"
        )
    return {
        "label": label,
        "seated": True,
        "residual_n": residual,
        "sum_n_kn": sum_n,
        "sum_fy_kn": sum_fy,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="../scratch/s73/case_straight_pair.json")
    parser.add_argument("--out", default="../scratch/s76")
    parser.add_argument("--seat-at", type=float, default=40.0)
    options = parser.parse_args()

    out = Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    source = Path(options.case)
    if not source.exists():
        raise SystemExit(f"missing {source}; run scripts/s73_straight_pair.py first")
    point_path = out / "case_straight_pair_point.json"
    point_path.write_text(json.dumps(_strip(source), ensure_ascii=False), encoding="utf-8")

    payload = {
        "strip": _report("strip", source, options.seat_at, out),
        "point": _report("point", point_path, options.seat_at, out),
    }
    (out / "normal_law.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(
        f"\nverdict: point law {'SEATS' if payload['point']['seated'] else 'FAILS'}; "
        f"strip law {'seats' if payload['strip']['seated'] else 'fails'}"
    )
    return 0 if payload["point"]["seated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
