"""Does the blade body, or the plain-rail gauge, break the straight-route seat?

Round 222's rigid straight case now has the correct crown geometry (measured crown-to-crown 1.493656 m
against wheel planes 1.493000 m), yet the vertical seat still refuses.  Two candidates remain and this
separates them by switching one thing at a time:

  ``blade``     the multi-body switch zone (stock and blade side by side, 50.578..57.304 m) -- its
                narrow ``zjg`` slices are the only unusual geometry in the case;
  ``no-blade``  the same table with the blade bodies' active window moved off the route, so the right
                rail is plain rail everywhere.

Whichever variant seats tells the next round where to look.  The seat's own refusal text is the result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from velch import vehicle_solver
from velch.vehicle import load_vehicle_case

EVEN_SHARE_N = 59_662.0


def body_stations(block: dict) -> list[dict]:
    if "stations" in block:
        return list(block["stations"])
    return [station for body in block["bodies"] for station in body["stations"]]


def seat(path: Path, *, label: str) -> None:
    case = load_vehicle_case(path)
    dynamics = vehicle_solver.VehicleDynamics(case)
    q = np.zeros(dynamics.dimension)
    v = np.zeros(dynamics.dimension)
    speed = float(case.vehicle.travel_speed_m_s)
    for index in range(len(case.wheels) // 2):
        v[dynamics.topology.require(f"wheelset{index + 1}", "spin")] = speed / float(
            case.vehicle.nominal_wheel_radius_m
        )
    try:
        seated, residual = vehicle_solver._seat(case, dynamics, q, v)
    except Exception as exc:
        print(f"{label:<10} {type(exc).__name__}: {str(exc)[:150]}")
        return
    dynamics.evaluate(0.0, seated, v)
    rows = []
    for rail_id, response in sorted(dynamics.body_contacts.items()):
        total = sum(float(item.normal_force_n) for item in (response if isinstance(response, tuple) else (response,))
                    if getattr(item, "active", False))
        if total > 0.0:
            rows.append((rail_id, total / EVEN_SHARE_N))
    print(f"{label:<10} seated residual {residual:.2e} N  loaded {len(rows)}/8  "
          + "  ".join(f"{rid} {ratio:.3f}x" for rid, ratio in rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--gap", type=float, default=1.4930)
    parser.add_argument("--out", type=Path, required=True)
    options = parser.parse_args()

    base = json.loads(Path(options.case).read_text(encoding="utf-8"))
    left = next(block for block in base["rail_templates"] if block["id"] == "left")
    left_y = min((abs(float(s["s_m"]) - 40.0), float(s["profile"]["y_offset_m"]))
                 for s in body_stations(left))[1]
    raw = json.loads(json.dumps(base))
    right = next(block for block in raw["rail_templates"] if block["id"] == "right")
    for station in body_stations(right):
        station["profile"]["y_offset_m"] = left_y + options.gap
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(json.dumps(raw), encoding="utf-8")
    seat(options.out, label="with-blade")

    raw = json.loads(json.dumps(base))
    right = next(block for block in raw["rail_templates"] if block["id"] == "right")
    for station in body_stations(right):
        station["profile"]["y_offset_m"] = left_y + options.gap
    for body in right.get("bodies", ()):
        if str(body.get("id", "")).endswith(":blade"):
            body["s_lo_m"], body["s_hi_m"] = 1.0e6, 1.0e6 + 1.0
    plain = options.out.with_name(options.out.stem + "_no_blade.json")
    plain.write_text(json.dumps(raw), encoding="utf-8")
    seat(plain, label="no-blade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
