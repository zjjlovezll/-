"""Does putting the creep coefficients on the measured contact ellipse change the curve?

Run order: build the R = 1100 m station-table curve, print what the patch implies for f11/f22 at the
seated state, then integrate 0.34 s with the flag on and off and compare the lateral force against the
21 842.4 N the curve needs.

The point of the exercise is not to tune anything: it is to see whether the *scale* of the creep
coefficients -- which the K22 measurement says is 3.5-5x below Kalker -- is what the curve is missing,
or whether the missing piece is somewhere else (cant, spin, the frozen 2.5 % tilt).
"""

from __future__ import annotations

import argparse
import importlib.util
import math
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _place_on_alignment, _seat

EVEN_SHARE_N = 59_662.0
DEMAND_N = 21_842.4  # m v^2 / R at R = 1100 m, 80 km/h (48 654 kg)


def _s32():
    path = Path(__file__).with_name("s32_curved_station_table.py")
    spec = importlib.util.spec_from_file_location("s32", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _print_patch(rows: list[tuple[str, float, float, float, float]]) -> None:
    print(f"{'rail':14s} {'N(kN)':>8s} {'b(mm)':>7s} {'f11(N)':>10s} {'f22(N)':>10s}")
    for rail, force, half_width, f11, f22 in rows:
        print(f"{rail:14s} {force / 1e3:8.2f} {half_width * 1e3:7.3f} {f11:10.4g} {f22:10.4g}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=0.34)
    parser.add_argument("--patch", action="store_true", help="enable the patch-based creep coefficients")
    options = parser.parse_args()

    s32 = _s32()
    case = s32.build(
        radius_m=1100.0,
        tangent_m=30.0,
        step_m=0.005,
        span_m=250.0,
        duration_s=options.duration,
        run_at_m=30.0,
        seat_at_m=30.0,
        curvature_force=True,
    )
    target = Path(case)
    import json

    raw = json.loads(target.read_text(encoding="utf-8"))
    if options.patch:
        raw["contact"]["creep_stiffness_from_patch"] = True
        out = target.with_name(target.stem + "_patchcreep.json")
        out.write_text(json.dumps(raw), encoding="utf-8")
        target = out
    loaded = load_vehicle_case(target)
    dynamics = VehicleDynamics(loaded)
    q = np.array(loaded.initial_q, dtype=float)
    velocity = np.array(loaded.initial_v, dtype=float)
    seated, residual = _seat(loaded, dynamics, q, velocity)
    seated = _place_on_alignment(loaded, dynamics, seated)
    speed = float(loaded.vehicle.travel_speed_m_s)
    for body in dynamics.topology.bodies:
        if body.id.startswith("wheelset") and "spin" in body.dof:
            velocity[dynamics.topology.require(body.id, "spin")] = speed / loaded.vehicle.nominal_wheel_radius_m
    dynamics.placement_enabled = True
    forces, contact_map = dynamics.evaluate(0.0, seated, velocity)
    law = loaded.contact
    rows = []
    for rail_id, response in contact_map.items():
        geometry = response.geometry
        if geometry is None or not response.active:
            continue
        half_a = (3.0 * response.normal_force_n * geometry.radius_star_m
                  / (4.0 * law.effective_modulus_pa)) ** (1.0 / 3.0) if geometry.radius_star_m > 0 else 0.0
        area = math.pi * half_a * geometry.half_width_m
        f11 = 2.0 * law.effective_modulus_pa * area / math.pi * law.creep_shape_x
        f22 = 2.0 * law.effective_modulus_pa * area / math.pi * law.creep_shape_lateral
        rows.append((rail_id, response.normal_force_n, geometry.half_width_m, f11, f22))
    print(f"case {target.name}, seat residual {residual:.3e} N, patch creep = {options.patch}")
    _print_patch(rows)
    if rows:
        print(f"median f11 {np.median([r[3] for r in rows]):.4g} N, f22 {np.median([r[4] for r in rows]):.4g} N"
              f" (frozen constants {law.creep_stiffness_x_n:.3g} / {law.creep_stiffness_lateral_n:.3g})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
