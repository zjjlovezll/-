"""Probe 5: locate the residual q-block error at t=0.45 / 0.70.

Part A: per-entry comparison of the assembled dq block against a central
        difference, printed worst first.
Part B: the strip-integral partials of the *geometry* at the same stations,
        against a direct finite difference of the band sum.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from velch.contact import (  # noqa: E402
    _absolute_arrays, _grid_slope, _strip_functional_partials)
from velch.jacobian import JacobianAssembler  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import (  # noqa: E402
    VehicleDynamics, _static_vertical_equilibrium)

SOURCE = HERE / "case_full12_cap05.json"
case = load_vehicle_case(SOURCE)
dynamics = VehicleDynamics(case)
q0 = np.array(case.initial_q, dtype=float)
v0 = np.array(case.initial_v, dtype=float)
q0, _res = _static_vertical_equilibrium(case, dynamics, q0, v0)
assembler = JacobianAssembler(dynamics)
law = case.contact
cfg = case.vehicle
n = q0.size

print("== Part A: assembled dq block vs central difference ==")
for t_s in (0.45, 0.70):
    jq, _jv = assembler.blocks(t_s, q0, v0)
    fd = np.zeros((n, n))
    for j in range(n):
        h = 1e-7 * max(1.0, abs(q0[j]))
        qp = q0.copy(); qp[j] += h
        qm = q0.copy(); qm[j] -= h
        fp = dynamics.derivative_pure(t_s, np.concatenate([qp, v0]))[n:]
        fm = dynamics.derivative_pure(t_s, np.concatenate([qm, v0]))[n:]
        fd[:, j] = (fp - fm) / (2.0 * h)
    scale = np.maximum(np.abs(fd).max(axis=0), 1e-30)
    err = np.abs(jq - fd) / scale[None, :]
    order = np.argsort(err.max(axis=0))[::-1][:6]
    print(f"\n t={t_s:.2f}")
    for j in order:
        i = int(np.argmax(err[:, j] / np.maximum(np.abs(fd[:, j]), 1e-30)))
        rel = abs(jq[i, j] - fd[i, j]) / max(abs(fd[i, j]), 1e-30)
        print(f"  col {j:2d} row {i:2d}  a={jq[i, j]:+.9e}  fd={fd[i, j]:+.9e}  colrel={err[:, j].max():.3e}")

print("\n== Part B: strip geometry partials vs FD of the band sum ==")
rail = case.rails[0]
wheel = dynamics.wheels[rail.wheel_id]
body = rail.contact_bodies[0]
wh = 5 * rail.axle_index
off = wheel.lateral_offset_m
E = law.effective_modulus_pa


def band(x, y_w, z_w, phi, ry, rz):
    sample = body.series.sample(x, 1)
    wy, wz, ry_, rz_ = _absolute_arrays(
        wheel.profile, sample, wheel_y_m=y_w, wheel_z_m=z_w, wheel_roll_rad=phi,
        wheel_lateral_offset_m=off, rail_y_m=ry, rail_z_m=rz)
    lower, upper = max(wy[0], ry_[0]), min(wy[-1], ry_[-1])
    span = upper - lower
    points = int(min(20001, max(64, math.ceil(span / law.strip_dy_m) + 1)))
    grid = np.linspace(lower, upper, points)
    step = float(grid[1] - grid[0])
    rzg = np.interp(grid, ry_, rz_)
    slope = _grid_slope(rzg, grid)
    wzg = np.interp(grid, wy, wz)
    inv = 1.0 / np.sqrt(1.0 + slope * slope)
    depth = (rzg - wzg) * inv
    engaged = depth > law.strip_min_depth_m
    weights = np.where(engaged, depth, 0.0)
    force = 0.25 * math.pi * E * float(np.sum(weights)) * step
    y_c = float(np.sum(grid * weights) / np.sum(weights))
    d_wheel_low = np.array([1.0, 0.0, -(wz[0] - z_w), 0.0, 0.0])
    d_wheel_up = np.array([1.0, 0.0, -(wz[-1] - z_w), 0.0, 0.0])
    d_rail = np.array([0.0, 0.0, 0.0, 1.0, 0.0])
    d_low = d_wheel_low if wy[0] >= ry_[0] else d_rail
    d_up = d_wheel_up if wy[-1] <= ry_[-1] else d_rail
    parts = _strip_functional_partials(
        grid=grid, rz=rzg, wz=wzg, slope=slope, inv=inv, weights=weights, step=step,
        wheel_y=wy, wheel_z=wz, rail_y=ry_, rail_z=rz_, wheel_y_m=y_w, wheel_z_m=z_w,
        wheel_roll_rad=phi, lower=lower, upper=upper, d_lower=d_low, d_upper=d_up,
        y_c=y_c, effective_modulus_pa=E)
    return force, y_c, parts, engaged


names = ["y_w", "z_w", "roll", "rail_y", "rail_z"]
for ri, rail_i in enumerate(case.rails):
    wheel_i = dynamics.wheels[rail_i.wheel_id]
    body_i = rail_i.contact_bodies[0]
    off_i = wheel_i.lateral_offset_m
    wh_i = 5 * rail_i.axle_index
    for t_s in (0.0, 0.45, 0.70):
        x = (case.run.x_start_m + cfg.travel_speed_m_s * t_s
             + cfg.axle_offsets_m[rail_i.axle_index])
        rail_y, rail_z, _vy, _vz = dynamics.track.local_state(
            q0, v0, ri, x, cfg.travel_speed_m_s)
        y_w = float(q0[wh_i]); z_w = cfg.wheel_center_height_m + float(q0[wh_i + 1])
        phi = float(q0[wh_i + 2])
        sample_i = body_i.series.sample(x, 1)

        def band_i(xx, yw, zw, ph, ry, rz, _b=body_i, _w=wheel_i, _o=off_i, _s=sample_i):
            wy, wz, ry_, rz_ = _absolute_arrays(
                _w.profile, _s, wheel_y_m=yw, wheel_z_m=zw, wheel_roll_rad=ph,
                wheel_lateral_offset_m=_o, rail_y_m=ry, rail_z_m=rz)
            lower, upper = max(wy[0], ry_[0]), min(wy[-1], ry_[-1])
            span = upper - lower
            points = int(min(20001, max(64, math.ceil(span / law.strip_dy_m) + 1)))
            grid = np.linspace(lower, upper, points)
            step = float(grid[1] - grid[0])
            rzg = np.interp(grid, ry_, rz_)
            slope = _grid_slope(rzg, grid)
            wzg = np.interp(grid, wy, wz)
            inv = 1.0 / np.sqrt(1.0 + slope * slope)
            depth = (rzg - wzg) * inv
            engaged = depth > law.strip_min_depth_m
            weights = np.where(engaged, depth, 0.0)
            force = 0.25 * math.pi * E * float(np.sum(weights)) * step
            y_c = float(np.sum(grid * weights) / np.sum(weights))
            d_low = (np.array([1.0, 0.0, -(wz[0] - zw), 0.0, 0.0]) if wy[0] >= ry_[0]
                     else np.array([0.0, 0.0, 0.0, 1.0, 0.0]))
            d_up = (np.array([1.0, 0.0, -(wz[-1] - zw), 0.0, 0.0]) if wy[-1] <= ry_[-1]
                    else np.array([0.0, 0.0, 0.0, 1.0, 0.0]))
            parts = _strip_functional_partials(
                grid=grid, rz=rzg, wz=wzg, slope=slope, inv=inv, weights=weights,
                step=step, wheel_y=wy, wheel_z=wz, rail_y=ry_, rail_z=rz_,
                wheel_y_m=yw, wheel_z_m=zw, wheel_roll_rad=ph, lower=lower,
                upper=upper, d_lower=d_low, d_upper=d_up, y_c=y_c,
                effective_modulus_pa=E)
            return force, y_c, parts, engaged, wy, ry_

        force, y_c, parts, engaged, wy, ry_ = band_i(x, y_w, z_w, phi, rail_y, rail_z)
        owned = ("wheel" if wy[0] >= ry_[0] else "rail",
                 "wheel" if wy[-1] <= ry_[-1] else "rail")
        tag = f"rail{ri}(axle{rail_i.axle_index}) t={t_s:.2f} x={x:.4f}"
        worst = 0.0
        for k, nm in enumerate(names):
            key = {"y_w": "y_w", "z_w": "z_w", "roll": "phi",
                   "rail_y": "ry", "rail_z": "rz"}[nm]
            args = dict(y_w=y_w, z_w=z_w, phi=phi, ry=rail_y, rz=rail_z)
            p = dict(args); m = dict(args)
            p[key] += 1e-7; m[key] -= 1e-7
            fdv = (band_i(x, p["y_w"], p["z_w"], p["phi"], p["ry"], p["rz"])[0]
                   - band_i(x, m["y_w"], m["z_w"], m["phi"], m["ry"], m["rz"])[0]) / 2e-7
            ana = parts.normal_force_n[k]
            rel = abs(ana - fdv) / max(abs(fdv), 1e-30)
            worst = max(worst, rel)
            if rel > 1e-6:
                print(f"   {tag} dN/d{nm:<7} a={ana:+.9e} fd={fdv:+.9e} rel={rel:.2e}")
        print(f"{tag} N={force:9.3f} y_c={y_c:+.9f} engaged={int(np.count_nonzero(engaged)):2d} "
              f"edge=({int(engaged[0])},{int(engaged[-1])}) bounds={owned} "
              f"worst={worst:.2e}")
