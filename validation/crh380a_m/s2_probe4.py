"""Probe 4: analytic band-sum derivatives of the strip integral vs FD ground truth."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from velch.contact import _absolute_arrays, _grid_slope  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import (  # noqa: E402
    VehicleDynamics, _static_vertical_equilibrium)

SOURCE = HERE / "case_full12_cap05.json"
case = load_vehicle_case(SOURCE)
dynamics = VehicleDynamics(case)
q0 = np.array(case.initial_q, dtype=float)
v0 = np.array(case.initial_v, dtype=float)
q0, _res = _static_vertical_equilibrium(case, dynamics, q0, v0)
law = case.contact
cfg = case.vehicle

rail = case.rails[0]
wheel = dynamics.wheels[rail.wheel_id]
body = rail.contact_bodies[0]
sample = body.series.sample(0.0, 1)
x = 0.0
rail_y, rail_z, _vy, _vz = dynamics.track.local_state(q0, v0, 0, x, cfg.travel_speed_m_s)
wh = 5 * rail.axle_index
y_w = float(q0[wh])
z_w = cfg.wheel_center_height_m + float(q0[wh + 1])
phi = float(q0[wh + 2])
off = wheel.lateral_offset_m

E = law.effective_modulus_pa
strip_dy = law.strip_dy_m
emin = law.strip_min_depth_m


def strip(y_w, z_w, phi, ry, rz, want_derivs=True):
    wy, wz_, ry_, rz_ = _absolute_arrays(
        wheel.profile, sample, wheel_y_m=y_w, wheel_z_m=z_w, wheel_roll_rad=phi,
        wheel_lateral_offset_m=off, rail_y_m=ry, rail_z_m=rz)
    lower = max(wy[0], ry_[0])
    upper = min(wy[-1], ry_[-1])
    span = upper - lower
    points = int(min(20001, max(64, math.ceil(span / strip_dy) + 1)))
    grid = np.linspace(lower, upper, points)
    step = float(grid[1] - grid[0])
    rzg = np.interp(grid, ry_, rz_)
    slope = _grid_slope(rzg, grid)
    wzg = np.interp(grid, wy, wz_)
    inv = 1.0 / np.sqrt(1.0 + slope * slope)
    depth = (rzg - wzg) * inv
    engaged = depth > emin
    weights = np.where(engaged, depth, 0.0)
    total = float(np.sum(weights)) * step
    force = 0.25 * math.pi * E * total
    y_c = float(np.sum(grid * weights) / np.sum(weights))
    if not want_derivs:
        return force, y_c, lower, upper
    # ---- analytic band-sum partials -------------------------------------
    def seg(x_nodes, z_nodes):
        """Exact slope of the piecewise-linear interpolant at each grid node."""
        j = np.clip(np.searchsorted(x_nodes, grid, side="left") - 1, 0, x_nodes.size - 2)
        return (z_nodes[j + 1] - z_nodes[j]) / (x_nodes[j + 1] - x_nodes[j])
    m_r = seg(ry_, rz_)
    m_w = seg(wy, wz_)
    ly = grid - y_w
    lz = wzg - z_w
    lam = (grid - lower) / span
    c, s = math.cos(phi), math.sin(phi)
    # bounds derivatives per column: order y_w, z_w, phi, rail_y, rail_z
    dlow = np.zeros(5)
    dupp = np.zeros(5)
    # wheel_y[0] = y_w + c*u0 - s*z0 ; wheel_y[-1] = y_w + c*u1 - s*z1
    u0 = off + float(wheel.profile.y_m[0]); z0 = float(wheel.profile.z_m[0])
    u1 = off + float(wheel.profile.y_m[-1]); z1 = float(wheel.profile.z_m[-1])
    dwy0 = np.array([1.0, 0.0, -s * u0 - c * z0, 0.0, 0.0])
    dwy1 = np.array([1.0, 0.0, -s * u1 - c * z1, 0.0, 0.0])
    dry0 = np.array([0.0, 0.0, 0.0, 1.0, 0.0])
    dry1 = np.array([0.0, 0.0, 0.0, 1.0, 0.0])
    if wy[0] >= ry_[0]:
        dlow = dwy0
    else:
        dlow = dry0
    if wy[-1] <= ry_[-1]:
        dupp = dwy1
    else:
        dupp = dry1
    dyi = dlow[None, :] + lam[:, None] * (dupp - dlow)[None, :]
    # wheel spatial slope at c/sin terms; per-column (d rz, d wz) at fixed y
    dwz = np.zeros((grid.size, 5))
    dwz[:, 0] = -m_w
    dwz[:, 1] = 1.0
    dwz[:, 2] = ly + m_w * lz
    drz = np.zeros((grid.size, 5))
    drz[:, 3] = -m_r
    drz[:, 4] = 1.0
    dslope = np.zeros((grid.size, 5))
    curv_r = _grid_slope(m_r, grid)
    for k in range(5):
        dslope[:, k] = curv_r * (dyi[:, k] - (1.0 if k == 3 else 0.0))
    dinv = (-slope * inv ** 3)[:, None] * dslope
    ddepth = (drz - dwz) * inv[:, None] + (rzg - wzg)[:, None] * dinv \
        + ((m_r - m_w) * inv)[:, None] * dyi
    mask = engaged[:, None].astype(float)
    ddepth *= mask
    dtotal = np.sum(ddepth, axis=0) * step
    dforce = 0.25 * math.pi * E * dtotal
    wsum = np.sum(weights)
    dyc = (np.sum(dyi * weights[:, None], axis=0)
           + np.sum(grid[:, None] * ddepth, axis=0)) / wsum \
        - y_c * np.sum(ddepth, axis=0) / wsum
    m_wc = float(np.interp(y_c, grid, m_w))
    m_rc = float(np.interp(y_c, grid, m_r))
    lyc, lzc = y_c - y_w, float(np.interp(y_c, grid, wzg)) - z_w
    dws = np.zeros(5)
    dws[0] = -m_wc; dws[1] = 1.0; dws[2] = lyc + m_wc * lzc
    dws = dws + m_wc * dyc
    drs = np.array([0.0, 0.0, 0.0, -m_rc, 1.0]) + m_rc * dyc
    dlever_y = dyc - np.array([1.0, 0.0, 0.0, 0.0, 0.0])
    dlever_z = dws - np.array([0.0, 1.0, 0.0, 0.0, 0.0])
    pen = (force / (4.0 / 3.0 * E * math.sqrt(0.6292))) ** (2.0 / 3.0)
    return dict(force=force, y_c=y_c, lower=lower, upper=upper, points=points,
                step=step, span=span, engaged=int(np.count_nonzero(engaged)),
                dforce=dforce, dyc=dyc, dlever_y=dlever_y, dlever_z=dlever_z,
                dws=dws, drs=drs, pen=pen)


base = strip(y_w, z_w, phi, rail_y, rail_z)
print(f"force={base['force']:.6f} y_c={base['y_c']:.9f} lower={base['lower']:.9f} "
      f"upper={base['upper']:.9f} span={base['span']*1e3:.4f}mm points={base['points']} "
      f"step={base['step']*1e3:.6f}mm engaged={base['engaged']}")
print(f"engaged_width={base['engaged']*base['step']*1e3:.4f} mm")

FD = {
    "force":  [-3.715280e7, -1.339899e9, +9.914450e8, +3.715e7, +1.339899e9],
    "y_c":    [-0.514034, -5.834866, +3.746292, +1.514034, +5.834866],
    "lever_z": [+0.035922, +0.138438, -0.830806, -0.035922, -0.138438],
    "lever_y": None,
}
names = ["y_w", "z_w", "roll", "rail_y", "rail_z"]

h = {"y_w": 1e-7, "z_w": 1e-7, "roll": 1e-7, "rail_y": 1e-7, "rail_z": 1e-7}
print("\ncol      quantity        analytic          fd          rel")
for k, nm in enumerate(names):
    kw = dict(y_w=y_w, z_w=z_w, phi=phi, ry=rail_y, rz=rail_z)
    key = {"y_w": "y_w", "z_w": "z_w", "roll": "phi", "rail_y": "ry", "rail_z": "rz"}[nm]
    kwp = dict(kw); kwm = dict(kw)
    kwp[key] += h[nm]; kwm[key] -= h[nm]
    p = strip(kwp["y_w"], kwp["z_w"], kwp["phi"], kwp["ry"], kwp["rz"], want_derivs=False)
    m = strip(kwm["y_w"], kwm["z_w"], kwm["phi"], kwm["ry"], kwm["rz"], want_derivs=False)
    parts = []
    for label, idx in (("force", 0), ("y_c", 1)):
        fdv = (p[idx] - m[idx]) / (2 * h[nm])
        ana = base["dforce"][k] if label == "force" else base["dyc"][k]
        parts.append((label, ana, fdv))
    # lever_z and lever_y via full geometry FD
    from velch.contact import find_graph_contact
    def geo(yw, zw, ph, ry, rz):
        return find_graph_contact(
            wheel.profile, sample, wheel_y_m=yw, wheel_z_m=zw, wheel_roll_rad=ph,
            wheel_lateral_offset_m=off, rail_y_m=ry, rail_z_m=rz,
            patch_half_width_m=law.patch_half_width_m, patch_slices=law.patch_slices,
            point_policy=law.point_policy, point_theta_m=law.point_theta_m,
            stiffness_policy=law.stiffness_policy,
            effective_modulus_pa=law.effective_modulus_pa,
            effective_radius_m=law.effective_radius_m,
            ellipticity_correction=law.ellipticity_correction,
            geometry_policy=law.geometry_policy, patch_window_m=law.patch_window_m,
            grid_step_m=law.grid_step_m, surface_key=(rail.id, body.id),
            normal_policy=law.normal_policy, strip_dy_m=law.strip_dy_m,
            strip_min_depth_m=law.strip_min_depth_m, strip_half_width_m=law.strip_half_width_m,
            strip_center_policy=law.strip_center_policy, curvature_policy=law.curvature_policy)
    gp = geo(kwp["y_w"], kwp["z_w"], kwp["phi"], kwp["ry"], kwp["rz"])
    gm = geo(kwm["y_w"], kwm["z_w"], kwm["phi"], kwm["ry"], kwm["rz"])
    for label, ana, f in (("lever_y", base["dlever_y"][k], (gp.lever_y_m - gm.lever_y_m) / (2 * h[nm])),
                          ("lever_z", base["dlever_z"][k], (gp.lever_z_m - gm.lever_z_m) / (2 * h[nm]))):
        parts.append((label, ana, f))
    for label, ana, fdv in parts:
        rel = abs(ana - fdv) / max(abs(fdv), 1e-12)
        print(f"{nm:>7} {label:>9} {ana:>+16.6e} {fdv:>+16.6e} {rel:>9.2e}")
