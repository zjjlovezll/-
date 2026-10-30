"""Run the R = 1100 m curve with the creep coefficients taken from the contact ellipse.

The question this answers is narrow and pre-registered: with the coefficients the *patch* implies
(11x / 23x the constants, or fewer once the band width is settled), does the curve reach the
21 842.4 N it needs and stay there -- or does it fail earlier, the way the flat x10 scale experiment
did (2.05 m instead of 4.53 m)?

Reported per run: status, frames, gates, the last-frame lateral force against the demand, the peak
to even-share ratio, and the deepest penetration.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

EVEN_SHARE_N = 59_662.0
DEMAND_N = 21_842.4


def _s32():
    path = Path(__file__).with_name("s32_curved_station_table.py")
    spec = importlib.util.spec_from_file_location("s32", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=0.34)
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    parser.add_argument("--creep", choices=("frozen", "patch"), default="patch")
    parser.add_argument("--creep-scale", type=float, default=None,
                        help="multiply the frozen constants instead of using the patch")
    options = parser.parse_args()

    s32 = _s32()
    target = Path(s32.build(
        radius_m=1100.0,
        tangent_m=30.0,
        step_m=0.005,
        span_m=250.0,
        duration_s=options.duration,
        run_at_m=30.0,
        seat_at_m=30.0,
        curvature_force=True,
    ))
    raw = json.loads(target.read_text(encoding="utf-8"))
    raw["vehicle"]["travel_speed_m_s"] = options.speed_kmh / 3.6
    if options.creep == "patch":
        raw["contact"]["creep_stiffness_from_patch"] = True
    if options.creep_scale is not None:
        raw["contact"]["creep_stiffness_x_n"] = 1.0e6 * options.creep_scale
        raw["contact"]["creep_stiffness_lateral_n"] = 5.0e5 * options.creep_scale
    out = target.with_name(f"{target.stem}_{options.creep}.json")
    out.write_text(json.dumps(raw), encoding="utf-8")
    case = load_vehicle_case(out)

    try:
        result = simulate_vehicle(case)
    except Exception as error:  # noqa: BLE001 - the failure text is the measurement
        print(f"{options.creep}: FAILED {type(error).__name__}: {error}")
        return 2

    summary = result.summary
    frames = int(summary.get("frames", 0))
    gates = summary.get("gates", {})
    passed = [name for name, ok in gates.items() if ok]
    failed = [name for name, ok in gates.items() if not ok]
    last = result.contacts[-1]
    lateral = 0.0
    peak = 0.0
    penetration = 0.0
    for rail_id, response in last.items():
        if response is None or response.geometry is None or not response.active:
            continue
        lateral += response.wheel_force_y_n
        peak = max(peak, response.normal_force_n)
        penetration = max(penetration, response.geometry.penetration_m)
    print(f"{options.creep}: status {summary.get('status')} frames {frames} "
          f"gates {len(passed)}/{len(gates)} failed {failed}")
    print(f"  last-frame sum Fy {lateral:+.1f} N = {100.0 * lateral / DEMAND_N:+.1f}% of demand")
    print(f"  peak normal {peak / 1e3:.1f} kN ({peak / EVEN_SHARE_N:.3f}x), max penetration {penetration * 1e6:.1f} um")
    print(f"  mileage travelled {result.positions[-1][0] - result.positions[0][0]:.3f} m" if result.positions else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
