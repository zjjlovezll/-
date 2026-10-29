"""Sweep the through-route offset difference and read the vertical seat.

Round 222 built a rigid straight case whose right rail is the through route (constant offset) and whose
left rail is untouched plain rail.  Three candidate offset differences all failed to seat:

    left + 1.50649  -> 8 of 8 wheels loaded, 21 531.3 N .. 97 829.0 N   (0.36x .. 1.64x)
    left + 1.47956  -> 4 of 8 wheels loaded, heaviest 130 347.9 N

The two rail families put their crowns about 6.8 mm outboard of their own midpoints (B041, round 216),
so an offset difference is not a gauge.  Rather than guess again, this measures the seat over a grid:
the crown-to-crown gauge is what the wheels feel, and the seat's load spread is the only honest vote.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from velch import vehicle_solver
from velch.vehicle import load_vehicle_case

EVEN_SHARE_N = 59_662.0
GAUGES = (1.4796, 1.4863, 1.4930, 1.4997, 1.5065)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--mileage", type=float, default=40.0)
    parser.add_argument("--gauges", type=float, nargs="+", default=None)
    options = parser.parse_args()

    base = json.loads(Path(options.case).read_text(encoding="utf-8"))
    left = next(block for block in base["rail_templates"] if block["id"] == "left")
    def stations_of(block: dict) -> list[dict]:
        """A template is either flat (``stations``) or split into ``bodies`` (the 220-era switch)."""
        if "stations" in block:
            return list(block["stations"])
        return [station for body in block["bodies"] for station in body["stations"]]

    left_y = min(
        ((abs(float(s["s_m"]) - options.mileage), float(s["profile"]["y_offset_m"]))
         for s in stations_of(left)),
    )[1]
    print(f"left offset at {options.mileage:.1f} m: {left_y:+.6f} m")
    scratch = Path(__file__).resolve().parents[2] / "scratch" / "s64"
    scratch.mkdir(parents=True, exist_ok=True)
    target = scratch / "sweep.json"
    speed = float(base["vehicle"]["travel_speed_m_s"])
    radius = float(base["vehicle"]["nominal_wheel_radius_m"])
    for gauge in (options.gauges or GAUGES):
        raw = json.loads(json.dumps(base))
        right = next(block for block in raw["rail_templates"] if block["id"] == "right")
        for station in stations_of(right):
            station["profile"]["y_offset_m"] = left_y + gauge
        target.write_text(json.dumps(raw), encoding="utf-8")
        case = load_vehicle_case(target)
        dynamics = vehicle_solver.VehicleDynamics(case)
        q = np.zeros(dynamics.dimension)
        v = np.zeros(dynamics.dimension)
        for index in range(len(case.wheels) // 2):
            v[dynamics.topology.require(f"wheelset{index + 1}", "spin")] = speed / radius
        try:
            seated, residual = vehicle_solver._seat(case, dynamics, q, v)
        except Exception as exc:  # the refusal text is the measurement
            print(f"  offset gap {gauge:.4f}: {type(exc).__name__}: {str(exc)[:130]}")
            continue
        dynamics.evaluate(0.0, seated, v)
        loads = {rid: sum(float(item.normal_force_n) for item in (resp if isinstance(resp, tuple) else (resp,))
                          if getattr(item, "active", False))
                 for rid, resp in dynamics.body_contacts.items()}
        ratios = np.array([load for load in loads.values() if load > 0.0]) / EVEN_SHARE_N
        print(f"  offset gap {gauge:.4f}: residual {residual:.2e} N  loaded {ratios.size}/8  "
              f"ratio {ratios.min():.3f}..{ratios.max():.3f}  sum {loads and sum(loads.values()) / EVEN_SHARE_N:.3f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
