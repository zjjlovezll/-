"""Probe 2: finite-difference the geometry map itself per coordinate."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from velch.contact import find_graph_contact  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import (  # noqa: E402
    VehicleDynamics, _static_vertical_equilibrium)

SOURCE = HERE / "case_full12_cap05.json"
case = load_vehicle_case(SOURCE)
dynamics = VehicleDynamics(case)
q0 = np.array(case.initial_q, dtype=float)
v0 = np.array(case.initial_v, dtype=float)
q0, residual = _static_vertical_equilibrium(case, dynamics, q0, v0)
n = dynamics.dimension
law = case.contact
cfg = case.vehicle


def geom_at(state_q, rail_index, t_s=0.0):
    rail = case.rails[rail_index]
    wh = 5 * rail.axle_index
    wheel = dynamics.wheels[rail.wheel_id]
    x = case.run.x_start_m + cfg.travel_speed_m_s * t_s + cfg.axle_offsets_m[rail.axle_index]
    rail_y, rail_z, _vy, _vz = dynamics.track.local_state(state_q, v0, rail_index, x,
                                                          cfg.travel_speed_m_s)
    out = []
    for body in rail.contact_bodies:
        if not body.active_at(x):
            continue
        sample = body.series.sample(x, 1)
        g = find_graph_contact(
            wheel.profile, sample, wheel_y_m=float(state_q[wh]),
            wheel_z_m=cfg.wheel_center_height_m + float(state_q[wh + 1]),
            wheel_roll_rad=float(state_q[wh + 2]),
            wheel_lateral_offset_m=wheel.lateral_offset_m,
            rail_y_m=rail_y, rail_z_m=rail_z,
            patch_half_width_m=law.patch_half_width_m, patch_slices=law.patch_slices,
            point_policy=law.point_policy, point_theta_m=law.point_theta_m,
            stiffness_policy=law.stiffness_policy,
            effective_modulus_pa=law.effective_modulus_pa,
            effective_radius_m=law.effective_radius_m,
            ellipticity_correction=law.ellipticity_correction,
            geometry_policy=law.geometry_policy, patch_window_m=law.patch_window_m,
            grid_step_m=law.grid_step_m, surface_key=(rail.id, body.id),
            normal_policy=law.normal_policy, strip_dy_m=law.strip_dy_m,
            strip_min_depth_m=law.strip_min_depth_m,
            strip_half_width_m=law.strip_half_width_m,
            strip_center_policy=law.strip_center_policy,
            curvature_policy=law.curvature_policy)
        out.append((body.id, g))
    return out


rail_index = 0
rail = case.rails[rail_index]
wh = 5 * rail.axle_index
base = geom_at(q0, rail_index)
print("base:", [(bid, None if g is None else (g.y_m, g.penetration_m)) for bid, g in base])

coords = [(wh, "y_w"), (wh + 1, "z_w"), (wh + 2, "roll"),
          (35 + 2 * rail_index, "rail_y"), (35 + 2 * rail_index + 1, "rail_z")]

fields = ["y_m", "penetration_m", "normal_y", "normal_z", "tangent_y", "tangent_z",
          "lever_y_m", "lever_z_m", "stiffness_n_m_1p5", "radius_star_m"]
for idx, name in coords:
    h = 1.0e-7 * max(1.0, abs(q0[idx]))
    if name == "roll":
        h = 1.0e-7
    qp = q0.copy(); qp[idx] += h
    qm = q0.copy(); qm[idx] -= h
    bp, bm = geom_at(qp, rail_index), geom_at(qm, rail_index)
    print(f"\n-- d/d{name} (h={h:.2e}) --")
    for (bid, gp), (_bid2, gm) in zip(bp, bm):
        g0 = dict((b, g) for b, g in base)[bid]
        if gp is None or gm is None:
            print(f"  {bid}: lost contact")
            continue
        parts = []
        for f in fields:
            a, b, c = getattr(gp, f), getattr(gm, f), getattr(g0, f)
            d = (a - b) / (2 * h)
            parts.append(f"{f}={c:.6g} d={d:+.6g}")
        print(f"  {bid}: " + "  ".join(parts))
print()
