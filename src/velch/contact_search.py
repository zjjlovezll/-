"""Contact point location: merged grid, patch quadratic, strip integral and splines.

Split out of :mod:`velch.contact`.  Each policy answers the same question — where does the
wheel touch the rail, how deep, and with which local normal — at a different cost and with a
different sliding behaviour, which is why they stay separate functions instead of one
switched body.
"""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from .contact_grid import (_RAIL_GRID_CACHE_SIZE, _build_rail_grid, _grid_curvature,
                           _grid_slope, _merge_grid, _rail_grid_cache,
                           _rail_node_slopes)
from .contact_law import (adaptive_theta_m, circular_equivalent_radius, hertz_half_width_m,
                          hertz_stiffness_n_m_1p5, local_curvature, quadratic_fit,
                          soft_argmax_position)
from .contact_models import ContactGeometry, ContactPartials
from .profiles import GraphProfile, ProfileError, ProfileSample


def _contact_on_span(
    wheel_y: np.ndarray,
    wheel_z: np.ndarray,
    rail_sample: ProfileSample,
    rail_y: np.ndarray,
    rail_z: np.ndarray,
    *,
    wheel_y_m: float,
    wheel_z_m: float,
    rail_y_m: float,
    lower: float,
    upper: float,
    patch_half_width_m: float = 0.0,
    patch_slices: int = 5,
    point_policy: str = "argmax",
    point_theta_m: float | None = None,
    stiffness_policy: str = "fixed_effective_radius",
    effective_modulus_pa: float | None = None,
    effective_radius_m: float | None = None,
    ellipticity_correction: float = 1.0,
    geometry_policy: str = "grid",
    grid_step_m: float = 0.0,
    surface_key: tuple[str, ...] | None = None,
) -> ContactGeometry | None:
    if upper <= lower:
        return None
    step = 0.0
    cache_key = None
    cached = None
    if geometry_policy == "cached_grid" and surface_key is not None:
        # The station identity, not the profile object: ProfileSeries may hand out a
        # fresh GraphProfile per sample, and keying on ``id`` would miss every call
        # (and could collide after a garbage collection).
        cache_key = ((surface_key, rail_sample.lower_s_m, rail_sample.upper_s_m,
                 float(rail_z[0]), float(rail_z[rail_z.size // 2]),
                 float(rail_z[-1]),
                 # The grid is built from ``rail_y`` as well: without a lateral fingerprint
                 # the cache swallowed lateral, gauge and roll irregularity (the default
                 # channel set), because those move the surface sideways, not vertically.
                 float(rail_y[0]), float(rail_y[rail_y.size // 2]),
                 float(rail_y[-1]))
                     if surface_key is not None else None)
        cached = _rail_grid_cache.get(cache_key) if cache_key is not None else None
        if cached is None:
            axis, axis_z, axis_slope, axis_step = _build_rail_grid(
                rail_y, rail_z, rail_sample, grid_step_m)
            cached = (axis, axis_z, axis_slope, axis_step)
            _rail_grid_cache[cache_key] = cached
            _rail_grid_cache.move_to_end(cache_key)
            while len(_rail_grid_cache) > _RAIL_GRID_CACHE_SIZE:
                _rail_grid_cache.popitem(last=False)
        else:
            _rail_grid_cache.move_to_end(cache_key)
    if geometry_policy == "fixed_grid" or geometry_policy == "cached_grid":
        if cached is not None:
            axis, axis_z, axis_slope, axis_step = cached
            first = int(np.searchsorted(axis, lower, side="left"))
            last = int(np.searchsorted(axis, upper, side="right"))
            if last - first < 2:
                return None
            grid = axis[first:last]
            r_z = axis_z[first:last]
            slopes = axis_slope[first:last]
            step = axis_step
        else:
            span = upper - lower
            step = (grid_step_m if grid_step_m > 0.0
                    else max(2.5e-5, min(2.0e-4, span / 1024.0)))
            count = max(2, int(math.floor(span / step)) + 1)
            step = span / (count - 1)
            grid = lower + step * np.arange(count, dtype=float)
            r_z = np.interp(grid, rail_y, rail_z)
            slopes = _grid_slope(r_z, grid)
    else:
        grid = _merge_grid(wheel_y, rail_y, lower, upper)
        if grid.size < 2:
            return None
        r_z = np.interp(grid, rail_y, rail_z)
        node_slopes = _rail_node_slopes(rail_y, rail_z, surface_key)
        slopes = (np.interp(grid, rail_y, node_slopes)
                  if node_slopes is not None else _grid_slope(r_z, grid))
    if grid.size < 2:
        return None
    w_z = np.interp(grid, wheel_y, wheel_z)
    inv_lengths = 1.0 / np.sqrt(1.0 + slopes * slopes)
    signed_depth = (r_z - w_z) * inv_lengths
    index = int(np.argmax(signed_depth))
    slope = float(slopes[index])
    inv = float(inv_lengths[index])
    y = float(grid[index])
    depth = float(signed_depth[index])
    wheel_z_on_grid = float(w_z[index])
    rail_z_on_grid = float(r_z[index])
    edge = index == 0 or index == grid.size - 1
    if geometry_policy in {"fixed_grid", "cached_grid"} and not edge:
        # Sub-grid refinement: the uniform grid places the extremum somewhere inside one
        # cell, so a parabola through the three cells around the maximum recovers the
        # continuous extremum instead of quantising the contact point to the grid.
        f0 = float(signed_depth[index - 1])
        f1 = float(signed_depth[index])
        f2 = float(signed_depth[index + 1])
        denominator = f0 - 2.0 * f1 + f2
        if denominator < 0.0:
            offset = 0.5 * (f0 - f2) / denominator
            if abs(offset) <= 1.0:
                refined = float(grid[index] + offset * step)
                if lower < refined < upper:
                    wheel_z_on_grid = float(np.interp(refined, grid, w_z))
                    rail_z_on_grid = float(np.interp(refined, grid, r_z))
                    slope = float(np.interp(refined, grid, slopes))
                    inv = float(1.0 / math.sqrt(1.0 + slope * slope))
                    refined_depth = (rail_z_on_grid - wheel_z_on_grid) * inv
                    if refined_depth >= depth:
                        y = refined
                        depth = refined_depth
    # Local stiffness and the physical patch size, both evaluated at the current
    # candidate point. A fixed effective radius stays available as the default;
    # the local policy derives R* from the curvature of the two profiles, which
    # makes a conformal flange root softer than the tread with no extra constant.
    radius_star = float(effective_radius_m or 0.0)
    stiffness = None
    if stiffness_policy == "local_circular" and effective_modulus_pa is not None:
        radius_y = max(1.0e-6, wheel_z_m - wheel_z_on_grid)
        radius_star = circular_equivalent_radius(
            radius_y, local_curvature(w_z, grid, y), local_curvature(r_z, grid, y),
            ellipticity=ellipticity_correction)
        stiffness = hertz_stiffness_n_m_1p5(effective_modulus_pa, radius_star)
    half_width = hertz_half_width_m(max(depth, 0.0), radius_star)
    if point_policy == "soft_argmax":
        theta = point_theta_m if point_theta_m is not None else adaptive_theta_m(half_width)
        centroid = soft_argmax_position(grid, signed_depth, theta)
        if centroid is not None:
            y = float(min(max(centroid, grid[0]), grid[-1]))
            depth = float(np.interp(y, grid, signed_depth))
            slope = float(np.interp(y, grid, slopes))
            inv = float(np.interp(y, grid, inv_lengths))
            wheel_z_on_grid = float(np.interp(y, grid, w_z))
            rail_z_on_grid = float(np.interp(y, grid, r_z))
            half_width = hertz_half_width_m(max(depth, 0.0), radius_star)
    if patch_half_width_m > 0.0:
        offsets = np.linspace(-patch_half_width_m, patch_half_width_m, patch_slices)
        sampled = np.interp(
            np.clip(y + offsets, grid[0], grid[-1]), grid, signed_depth
        )
        positive = np.maximum(sampled, 0.0)
        depth = float(np.mean(positive ** 1.5) ** (2.0 / 3.0))
        half_width = max(half_width, patch_half_width_m)
    dz_ds = float(np.interp(y - rail_y_m, rail_sample.profile.y_m, rail_sample.dz_ds))
    if depth > 0 and not math.isfinite(dz_ds):
        raise ProfileError("longitudinal profile derivative is undefined at the contact point")
    return ContactGeometry(
        y_m=y,
        wheel_z_m=wheel_z_on_grid,
        rail_z_m=rail_z_on_grid,
        penetration_m=max(0.0, depth),
        normal_y=-slope * inv,
        normal_z=inv,
        tangent_y=inv,
        tangent_z=slope * inv,
        lever_y_m=y - wheel_y_m,
        lever_z_m=wheel_z_on_grid - wheel_z_m,
        rail_dz_ds=dz_ds,
        edge_limited=edge,
        stiffness_n_m_1p5=stiffness,
        radius_star_m=radius_star,
        half_width_m=half_width,
    )


def _absolute_arrays(wheel_profile, rail_sample, *, wheel_y_m: float, wheel_z_m: float,
                     wheel_roll_rad: float, wheel_lateral_offset_m: float,
                     rail_y_m: float, rail_z_m: float):
    """Place both bands in the track frame (the one transform both paths share)."""
    local_y = wheel_lateral_offset_m + wheel_profile.y_m
    local_z = wheel_profile.z_m
    c, s = math.cos(wheel_roll_rad), math.sin(wheel_roll_rad)
    wheel_y = wheel_y_m + c * local_y - s * local_z
    wheel_z = wheel_z_m + s * local_y + c * local_z
    rail_y = rail_y_m + rail_sample.profile.y_m
    rail_z = rail_z_m + rail_sample.profile.z_m
    return wheel_y, wheel_z, rail_y, rail_z


def _window_quadratic(y: np.ndarray, z: np.ndarray, y0: float, half_span: float,
                      minimum_points: int = 5):
    """Least-squares quadratic of ``z(y)`` about ``y0`` over ``±half_span``."""
    # ``y`` is ascending, so the window is a contiguous slice. Slicing by
    # searchsorted avoids a full-length boolean mask and its fancy-index copy on
    # every evaluation, which was most of this function's cost on a 2000-node rail.
    low = int(np.searchsorted(y, y0 - half_span, side="left"))
    high = int(np.searchsorted(y, y0 + half_span, side="right"))
    if high - low < minimum_points:
        return None
    t = y[low:high] - y0
    if float(t[-1] - t[0]) < 0.6 * half_span:
        return None
    return quadratic_fit(t, z[low:high])


def find_patch_contact(
    wheel_profile: GraphProfile,
    rail_sample: ProfileSample,
    *,
    wheel_y_m: float,
    wheel_z_m: float,
    wheel_roll_rad: float,
    wheel_lateral_offset_m: float,
    rail_y_m: float,
    rail_z_m: float,
    window_m: float = 1.0e-3,
    iterations: int = 2,
    effective_modulus_pa: float | None = None,
    effective_radius_m: float | None = None,
    ellipticity_correction: float = 1.0,
) -> ContactGeometry | None:
    """Contact refined to the extremum of a patch-scale quadratic, not a grid node.

    The grid path returns the deepest *node* of a merged sampling grid, so the
    contact rides from node to node and the surface normal jumps each time. That
    jump is a numerical artefact, and on a smooth run it shows up as a force
    ripple at a frequency set by the node spacing, not by the vehicle.

    Here the coarse grid only proposes a bracket. Both surfaces are then replaced
    by least-squares quadratics over a window of the contact-patch scale, the
    clearance extremum is solved analytically inside that window, and the
    curvature that feeds ``R*`` comes from the same quadratics. No extra constant
    is introduced: ``window_m`` is the only knob and it defaults to the same
    1 mm that the grid path already uses to measure curvature.
    """
    wheel_y, wheel_z, rail_y, rail_z = _absolute_arrays(
        wheel_profile, rail_sample, wheel_y_m=wheel_y_m, wheel_z_m=wheel_z_m,
        wheel_roll_rad=wheel_roll_rad,
        wheel_lateral_offset_m=wheel_lateral_offset_m,
        rail_y_m=rail_y_m, rail_z_m=rail_z_m)
    lower, upper = max(wheel_y[0], rail_y[0]), min(wheel_y[-1], rail_y[-1])
    if upper <= lower:
        return None
    span = upper - lower
    step = min(2.0e-4, span / 8.0)
    scan = np.arange(lower, upper + 0.5 * step, step)
    if scan.size < 3:
        return None
    wz_scan = np.interp(scan, wheel_y, wheel_z)
    rz_scan = np.interp(scan, rail_y, rail_z)
    slope_scan = _grid_slope(rz_scan, scan)
    depth_scan = (rz_scan - wz_scan) / np.sqrt(1.0 + slope_scan * slope_scan)
    count = int(depth_scan.size)
    index = int(np.argmax(depth_scan))
    y_grid = float(scan[index])
    depth_grid = float(depth_scan[index])
    y0 = y_grid
    # Sub-node refinement only: a parabola through the three nodes that straddle
    # the sampled maximum. It cannot smooth anything wider than one node, so a
    # 1.4 mm notch is still seen as a notch; the only change is that the contact
    # point stops jumping from node to node as the wheel rolls.
    wheel_quad = None
    rail_quad = None
    if 0 < index < count - 1:
        triple = scan[index - 1:index + 2]
        local = triple - y_grid
        wheel_quad = quadratic_fit(local, np.interp(triple, wheel_y, wheel_z))
        rail_quad = quadratic_fit(local, np.interp(triple, rail_y, rail_z))
        curvature = rail_quad[0] - wheel_quad[0]
        if curvature < 0.0:
            candidate = y_grid - (rail_quad[1] - wheel_quad[1]) / (2.0 * curvature)
            y0 = float(min(max(candidate, float(triple[0])), float(triple[-1])))
    if wheel_quad is None or rail_quad is None:
        wheel_surface = float(np.interp(y_grid, wheel_y, wheel_z))
        rail_surface = float(np.interp(y_grid, rail_y, rail_z))
        slope = float(np.interp(y_grid, rail_y,
                                _grid_slope(rail_z, rail_y)))
        inv = 1.0 / math.sqrt(1.0 + slope * slope)
        depth = (rail_surface - wheel_surface) * inv
    else:
        offset = y0 - y_grid
        wheel_surface = float(np.polyval(wheel_quad, offset))
        rail_surface = float(np.polyval(rail_quad, offset))
        slope = float(2.0 * rail_quad[0] * offset + rail_quad[1])
        inv = 1.0 / math.sqrt(1.0 + slope * slope)
        depth = (rail_surface - wheel_surface) * inv
        if depth <= 0.0 and depth_grid > 0.0:
            # The parabola says no contact where the sampled surface says contact:
            # trust the samples (a sharp V is not a parabola).
            y0 = y_grid
            wheel_surface = float(np.interp(y_grid, wheel_y, wheel_z))
            rail_surface = float(np.interp(y_grid, rail_y, rail_z))
            slope = float(rail_quad[1])
            inv = 1.0 / math.sqrt(1.0 + slope * slope)
            depth = depth_grid
    half_span = max(float(window_m), 2.5 * max(
        float(np.median(np.diff(wheel_y))), float(np.median(np.diff(rail_y)))))
    stiff_wheel = _window_quadratic(wheel_y, wheel_z, y0, half_span)
    stiff_rail = _window_quadratic(rail_y, rail_z, y0, half_span)
    curvature_wheel = 2.0 * float((stiff_wheel if stiff_wheel is not None
                                   else (wheel_quad if wheel_quad is not None
                                         else np.zeros(3)))[0])
    curvature_rail = 2.0 * float((stiff_rail if stiff_rail is not None
                                  else (rail_quad if rail_quad is not None
                                        else np.zeros(3)))[0])
    radius_star = float(effective_radius_m or 0.0)
    stiffness = None
    if effective_modulus_pa is not None:
        radius_y = max(1.0e-6, wheel_z_m - wheel_surface)
        total = 1.0 / radius_y + abs(curvature_wheel) + abs(curvature_rail)
        radius_star = (ellipticity_correction * 4.0 / total if total > 0.0
                       else radius_y)
        stiffness = 4.0 / 3.0 * effective_modulus_pa * math.sqrt(radius_star)
    penetration = max(0.0, depth)
    half_width = (math.sqrt(2.0 * radius_star * penetration)
                  if penetration > 0.0 and radius_star > 0.0 else 0.0)
    dz_ds = float(np.interp(y0 - rail_y_m, rail_sample.profile.y_m, rail_sample.dz_ds))
    if depth > 0 and not math.isfinite(dz_ds):
        raise ProfileError("longitudinal profile derivative is undefined at the contact point")
    return ContactGeometry(
        y_m=y0,
        wheel_z_m=wheel_surface,
        rail_z_m=rail_surface,
        penetration_m=penetration,
        normal_y=-slope * inv,
        normal_z=inv,
        tangent_y=inv,
        tangent_z=slope * inv,
        lever_y_m=y0 - wheel_y_m,
        lever_z_m=wheel_surface - wheel_z_m,
        rail_dz_ds=dz_ds,
        edge_limited=bool(y0 <= lower + 1e-12 or y0 >= upper - 1e-12),
        stiffness_n_m_1p5=stiffness,
        radius_star_m=radius_star,
        half_width_m=half_width,
    )


def _deepest_depth_y(
    wheel_profile: GraphProfile,
    rail_sample: ProfileSample,
    *,
    wheel_y_m: float,
    wheel_z_m: float,
    wheel_roll_rad: float,
    wheel_lateral_offset_m: float,
    rail_y_m: float,
    rail_z_m: float,
    step_m: float,
) -> float | None:
    """Lateral position of the hardest-pressed strip over the whole overlap.

    Used to centre a bounded strip patch: the patch has to sit on the contact the
    geometry actually produces, not on the centroid of everything the wheel can
    see.  Coarse by design -- only the location is consumed, the force still comes
    from the fine strip integral.
    """
    wheel_y, wheel_z, rail_y, rail_z = _absolute_arrays(
        wheel_profile, rail_sample, wheel_y_m=wheel_y_m, wheel_z_m=wheel_z_m,
        wheel_roll_rad=wheel_roll_rad,
        wheel_lateral_offset_m=wheel_lateral_offset_m,
        rail_y_m=rail_y_m, rail_z_m=rail_z_m)
    lower, upper = max(wheel_y[0], rail_y[0]), min(wheel_y[-1], rail_y[-1])
    if upper <= lower:
        return None
    points = int(min(20001, max(16, math.ceil((upper - lower) / step_m) + 1)))
    grid = np.linspace(lower, upper, points)
    rz = np.interp(grid, rail_y, rail_z)
    wz = np.interp(grid, wheel_y, wheel_z)
    slope = _grid_slope(rz, grid)
    depth = (rz - wz) / np.sqrt(1.0 + slope * slope)
    return float(grid[int(np.argmax(depth))])


def _segment_slope(x_nodes: np.ndarray, z_nodes: np.ndarray,
                   at: np.ndarray | float) -> np.ndarray:
    """Slope of the piecewise-linear surface through ``(x_nodes, z_nodes)`` at ``at``.

    This is the exact segment slope of the sampled surface, i.e. the derivative
    of ``np.interp`` itself. ``_grid_slope`` (a central difference on the merged
    grid) is the right thing for the *value* of the force but a smeared surface
    for the *derivative*: differentiating it costs ~5e-3 relative on ``dN/dq``.
    """
    index = np.clip(np.searchsorted(x_nodes, at, side="left") - 1, 0, x_nodes.size - 2)
    return np.diff(z_nodes)[index] / np.diff(x_nodes)[index]


def _strip_functional_partials(
    *,
    grid: np.ndarray,
    rz: np.ndarray,
    wz: np.ndarray,
    slope: np.ndarray,
    inv: np.ndarray,
    weights: np.ndarray,
    step: float,
    wheel_y: np.ndarray,
    wheel_z: np.ndarray,
    rail_y: np.ndarray,
    rail_z: np.ndarray,
    wheel_y_m: float,
    wheel_z_m: float,
    wheel_roll_rad: float,
    lower: float,
    upper: float,
    d_lower: np.ndarray,
    d_upper: np.ndarray,
    y_c: float,
    effective_modulus_pa: float,
    angle_interpolated: bool,
    dz_ds_slope: float = 0.0,
) -> ContactPartials:
    """Derive ``d(normal force)/dq`` and ``d(lever arms)/dq`` for a strip contact.

    Mode order is :data:`CONTACT_MODES`. The wheel surface is a rotated profile,
    ``Y(u) = y_w + c u - s z(u)``, ``Z(u) = z_w + s u + c z(u)`` with
    ``(c, s) = (cos roll, sin roll)``; the rail is ``rail_z(y) = z_r + P_r(y - y_r)``.
    Differentiating at *fixed spatial y* (which is what the depth field is
    sampled on) gives, per strip,

    * ``dZ/dy_w = -m_w``, ``dZ/dz_w = 1``, ``d(rail_z)/dy_r = -m_r``, ``d/dz_r = 1``
      -- the profile slopes, not the normal components, and
    * ``dY/droll = -(Z - z_w)``, ``dZ/droll = +(Y - y_w)``, i.e. the rotation of a
      rigid body about the wheel centre (``u`` and ``z(u)`` cancel identically,
      so no profile data and no sign convention is needed here).

    ``d(depth)/dq = inv d(rail_z - wheel_z)/dq + (rail_z - wheel_z) d(inv)/dq
    + inv (m_r - m_w) dy_i/dq``: the last two terms are the node sliding along the
    rail (window motion and the rail's own curvature). The elastic force gradient
    is ``(pi/4) E* sum d(depth)/dq step`` -- for ``strip_min_depth_m == 0`` the
    engaged set's boundary sits at zero depth, so the moving boundary contributes
    nothing and this sum is exact.
    """
    count = grid.size
    # The uniform grid is anchored to the overlap bounds, so every node slides
    # with them by a fixed fraction of the window.
    lam = (grid - lower) / (upper - lower)
    d_grid = (d_lower[None, :] * (1.0 - lam)[:, None] + d_upper[None, :] * lam[:, None])
    m_w = _segment_slope(wheel_y, wheel_z, grid)
    m_r = _segment_slope(rail_y, rail_z, grid)
    ly = grid - wheel_y_m
    lz = wz - wheel_z_m
    # Per-node partials of the two surface heights at fixed spatial y.
    d_rz = np.zeros((count, 5))
    d_rz[:, 3] = -m_r
    d_rz[:, 4] = 1.0
    d_wz = np.zeros((count, 5))
    d_wz[:, 0] = -m_w
    d_wz[:, 1] = 1.0
    d_wz[:, 2] = ly + m_w * lz
    # inv = (1 + slope^2)^-1/2 with slope the rail's own slope at the node.  The
    # derivative of that finite-difference slope field with respect to a shift of
    # the sampling is the same finite difference applied again -- not the slope of
    # the exact piecewise-linear interpolant, which is a staircase on the strip
    # grid and overestimates the curvature wherever the grid is coarser than the
    # profile nodes.
    curvature = _grid_slope(slope, grid)
    d_slope = curvature[:, None] * d_grid
    d_slope[:, 3] -= curvature  # a unit rail_y shift steepens the rail under the node
    d_inv = -slope[:, None] * inv[:, None] ** 3 * d_slope
    d_depth = (inv[:, None] * (d_rz - d_wz) + (rz - wz)[:, None] * d_inv
               + inv[:, None] * (m_r - m_w)[:, None] * d_grid)
    d_depth *= (weights > 0.0)[:, None]
    normal_force = 0.25 * math.pi * effective_modulus_pa * np.sum(d_depth, axis=0) * step
    # Contact centroid: a weighted mean of the grid, so both the weights and the
    # abscissae move.
    weight_sum = float(np.sum(weights))
    d_weight_sum = np.sum(d_depth, axis=0)
    d_y_c = ((np.sum(d_grid * weights[:, None], axis=0)
              + np.sum(grid[:, None] * d_depth, axis=0)) / weight_sum
             - y_c * d_weight_sum / weight_sum)
    d_lever_y = d_y_c.copy()
    d_lever_y[0] -= 1.0
    # The wheel surface under the centroid slides beneath the fixed node.
    slope_y_c = float(_segment_slope(wheel_y, wheel_z, y_c))
    lever_z_c = float(np.interp(y_c, grid, wz)) - wheel_z_m
    lever_y_c = y_c - wheel_y_m
    d_surface = np.array([-slope_y_c, 1.0, lever_y_c + slope_y_c * lever_z_c, 0.0, 0.0])
    d_surface += slope_y_c * d_y_c
    d_lever_z = d_surface.copy()
    d_lever_z[1] -= 1.0
    # The reported angle is read off the sampled slope *field*: under a rail shift
    # the field travels with the rail (its nodes do too), so only the centroid's
    # motion relative to the rail moves the reading. On the hardest-strip branch the
    # reading is a lookup in a piecewise-constant array and does not move at all.
    if angle_interpolated:
        d_angle = (float(_segment_slope(grid, slope, y_c))
                   * (d_y_c - np.array([0.0, 0.0, 0.0, 1.0, 0.0])))
    else:
        d_angle = np.zeros(5)
    # ``rail_dz_ds`` is read off the profile at ``y_c - rail_y_m``, i.e. in the rail's
    # own lateral coordinate, so a rail translation carries the field with it and only
    # the centroid's motion relative to the rail changes the reading.
    d_dz_ds = dz_ds_slope * (d_y_c - np.array([0.0, 0.0, 0.0, 1.0, 0.0]))
    return ContactPartials(
        normal_force_n=tuple(float(v) for v in normal_force),
        lever_y_m=tuple(float(v) for v in d_lever_y),
        lever_z_m=tuple(float(v) for v in d_lever_z),
        normal_slope=tuple(float(v) for v in d_angle),
        rail_dz_ds=tuple(float(v) for v in d_dz_ds),
    )


def find_strip_contact(
    wheel_profile: GraphProfile,
    rail_sample: ProfileSample,
    *,
    wheel_y_m: float,
    wheel_z_m: float,
    wheel_roll_rad: float,
    wheel_lateral_offset_m: float,
    rail_y_m: float,
    rail_z_m: float,
    strip_dy_m: float = 2.5e-4,
    strip_min_depth_m: float = 0.0,
    center_y_m: float | None = None,
    half_width_m: float | None = None,
    clip_to_engaged_run: bool = False,
    effective_modulus_pa: float | None = None,
    effective_radius_m: float | None = None,
    ellipticity_correction: float = 1.0,
    stiffness_policy: str = "fixed_effective_radius",
    curvature_policy: str = "window",
    geometry_policy: str = "grid",
    grid_step_m: float = 0.0,
    surface_key: tuple[str, ...] | None = None,
    partials: bool = False,
) -> ContactGeometry | None:
    """Normal force integrated over every engaged strip instead of one point.

    Each strip carries the plane-strain Hertzian line load of a cylinder on a
    plane, ``n = (π/4) E* δ`` per unit width. Summing over the engaged band keeps
    a finite force while the hardest-pressed strip unloads, which is what a real
    contact patch does and what a single-point law cannot do.

    The result is returned as a *consistent pair*: an equivalent penetration
    ``δ_eq`` plus the single-point stiffness ``C`` with ``N = C δ_eq^1.5``. The
    rest of the chain (damping, friction saturation, history channels) then runs
    unchanged and still reproduces the integrated force exactly.
    """
    if effective_modulus_pa is None:
        raise ValueError(
            "strip_integral needs the effective modulus; set contact.stiffness_policy "
            "to 'local_circular' so the case supplies it")
    if not math.isfinite(strip_dy_m) or strip_dy_m <= 0.0:
        raise ValueError("strip_dy_m must be positive and finite")
    wheel_y, wheel_z, rail_y, rail_z = _absolute_arrays(
        wheel_profile, rail_sample, wheel_y_m=wheel_y_m, wheel_z_m=wheel_z_m,
        wheel_roll_rad=wheel_roll_rad,
        wheel_lateral_offset_m=wheel_lateral_offset_m,
        rail_y_m=rail_y_m, rail_z_m=rail_z_m)
    lower, upper = max(wheel_y[0], rail_y[0]), min(wheel_y[-1], rail_y[-1])
    if upper <= lower:
        return None
    full_lower, full_upper = lower, upper
    if center_y_m is not None and half_width_m is not None and half_width_m > 0.0:
        # Bounded patch: integrate around the deepest point rather than across the
        # whole overlap.  The whole-overlap form is what lets a flangeway recess or
        # a seat cut contribute to the normal force (596 kN / 0.30 mm lift history).
        lower = max(lower, center_y_m - half_width_m)
        upper = min(upper, center_y_m + half_width_m)
        if upper <= lower:
            return None
    span = upper - lower
    grid = None
    uniform_grid = False
    if geometry_policy == "cached_grid" and surface_key is not None:
        # The rail half of the stationary grid does not depend on the wheelset, so it
        # is built once per station and sliced here; only the wheel interpolation
        # remains per call.
        key = ((surface_key, rail_sample.lower_s_m, rail_sample.upper_s_m,
                 float(rail_z[0]), float(rail_z[rail_z.size // 2]),
                 float(rail_z[-1]),
                 float(rail_y[0]), float(rail_y[rail_y.size // 2]),
                 float(rail_y[-1]))
               if surface_key is not None else None)
        cached = _rail_grid_cache.get(key) if key is not None else None
        if cached is None:
            cached = _build_rail_grid(rail_y, rail_z, rail_sample,
                                      grid_step_m if grid_step_m > 0.0 else strip_dy_m)
            _rail_grid_cache[key] = cached
            while len(_rail_grid_cache) > _RAIL_GRID_CACHE_SIZE:
                _rail_grid_cache.popitem(last=False)
        else:
            _rail_grid_cache.move_to_end(key)
        axis, axis_z, axis_slope, axis_step = cached
        first = int(np.searchsorted(axis, lower, side="left"))
        last = int(np.searchsorted(axis, upper, side="right"))
        if last - first >= 8:
            grid = axis[first:last]
            rz = axis_z[first:last]
            slope = axis_slope[first:last]
            step = axis_step
    if grid is None:
        uniform_grid = True
        points = int(min(20001, max(64, math.ceil(span / strip_dy_m) + 1)))
        grid = np.linspace(lower, upper, points)
        step = float(grid[1] - grid[0])
        rz = np.interp(grid, rail_y, rail_z)
        slope = _grid_slope(rz, grid)
    wz = np.interp(grid, wheel_y, wheel_z)
    inv = 1.0 / np.sqrt(1.0 + slope * slope)
    depth = (rz - wz) * inv
    engaged = depth > strip_min_depth_m
    if clip_to_engaged_run and bool(np.any(engaged)):
        # Adaptive patch width: keep only the engaged run that carries the deepest
        # strip.  A fixed half-width has no defensible value -- 3..5 mm suppresses the
        # contact loss on the frog while 6..10 mm reproduces it exactly, because a
        # wider window reaches across a flangeway or a seat cut and picks up a second,
        # non-load-bearing surface.  The engaged run *is* that boundary, measured
        # instead of guessed, and it widens automatically on plain track.
        index = int(np.argmax(depth))
        lo = index
        while lo > 0 and engaged[lo - 1]:
            lo -= 1
        hi = index
        while hi + 1 < engaged.size and engaged[hi + 1]:
            hi += 1
        if lo > 0 or hi + 1 < engaged.size:
            mask = np.zeros(engaged.size, dtype=bool)
            mask[lo:hi + 1] = True
            engaged = engaged & mask
    if not bool(np.any(engaged)):
        return None
    weights = np.where(engaged, depth, 0.0)
    total = float(np.sum(weights)) * step
    if total <= 0.0:
        return None
    force = 0.25 * math.pi * effective_modulus_pa * total
    y_c = float(np.sum(grid * weights) / np.sum(weights))
    index = int(np.argmax(depth))
    if abs(grid[index] - y_c) > 0.25 * step:
        # Keep the reported angle at the hardest-pressed strip: the centroid of a
        # two-shoulder contact can sit in the notch between them, where neither
        # surface's slope describes the contact.
        slope_at = float(slope[index])
    else:
        slope_at = float(np.interp(y_c, grid, slope))
    inv_at = 1.0 / math.sqrt(1.0 + slope_at * slope_at)
    half_span = max(1.0e-3, 2.5 * wheel_profile.node_spacing_m,
                    2.5 * rail_sample.profile.node_spacing_m)
    if curvature_policy == "grid_stencil":
        # Second difference on the merged grid already built above: two extra
        # vectorised passes instead of two window fits over the raw node lists.
        wheel_curvature = float(np.interp(y_c, grid, _grid_curvature(wz, grid)))
        rail_curvature = float(np.interp(y_c, grid, _grid_curvature(rz, grid)))
    else:
        wheel_quad = _window_quadratic(wheel_y, wheel_z, y_c, half_span)
        rail_quad = _window_quadratic(rail_y, rail_z, y_c, half_span)
        wheel_curvature = abs(2.0 * float(wheel_quad[0])) if wheel_quad is not None else None
        rail_curvature = abs(2.0 * float(rail_quad[0])) if rail_quad is not None else None
    wheel_surface = float(np.interp(y_c, wheel_y, wheel_z))
    rail_surface = float(np.interp(y_c, rail_y, rail_z))
    radius_y = max(1.0e-6, wheel_z_m - wheel_surface)
    if (stiffness_policy == "local_circular"
            and wheel_curvature is not None and rail_curvature is not None):
        total_curvature = (1.0 / radius_y + wheel_curvature + rail_curvature)
        radius_star = (ellipticity_correction * 4.0 / total_curvature
                       if total_curvature > 0.0 else radius_y)
    else:
        radius_star = float(effective_radius_m or radius_y)
    point_stiffness = 4.0 / 3.0 * effective_modulus_pa * math.sqrt(radius_star)
    penetration = (force / point_stiffness) ** (2.0 / 3.0)
    engaged_width = float(np.count_nonzero(engaged)) * step
    dz_ds = float(np.interp(y_c - rail_y_m, rail_sample.profile.y_m, rail_sample.dz_ds))
    if not math.isfinite(dz_ds):
        raise ProfileError("longitudinal profile derivative is undefined at the contact point")
    contact_partials = None
    if partials and uniform_grid:
        # ``cached_grid`` samples fixed rail-frame nodes, so the window's nodes do
        # not translate with the overlap bounds; that variant keeps the point form.
        d_lower = np.zeros(5)
        d_upper = np.zeros(5)
        # d(wheel_y)/dq at the two profile ends. The roll entry is
        # -(wheel_z - wheel_z_m), exactly: a rigid rotation about the wheel centre
        # carries u and z(u) with it, so neither the profile nor its sign
        # convention enters, and it cancels the same way in d(wheel_z)/d(roll) =
        # +(wheel_y - wheel_y_m).
        d_wheel_low = np.array(
            [1.0, 0.0, -(wheel_z[0] - wheel_z_m), 0.0, 0.0])
        d_wheel_up = np.array(
            [1.0, 0.0, -(wheel_z[-1] - wheel_z_m), 0.0, 0.0])
        d_rail = np.array([0.0, 0.0, 0.0, 1.0, 0.0])
        if center_y_m is not None and half_width_m is not None and half_width_m > 0.0:
            # A bounded patch window overrides the overlap bounds; its centre is not
            # differentiated (the patch is a modelling choice, not a contact map).
            clamped = (lower > full_lower + 0.0) or (upper < full_upper - 0.0)
            d_lower = np.zeros(5) if clamped else (d_wheel_low if wheel_y[0] >= rail_y[0]
                                                   else d_rail)
            d_upper = np.zeros(5) if clamped else (d_wheel_up if wheel_y[-1] <= rail_y[-1]
                                                   else d_rail)
        else:
            d_lower = d_wheel_low if wheel_y[0] >= rail_y[0] else d_rail
            d_upper = d_wheel_up if wheel_y[-1] <= rail_y[-1] else d_rail
        contact_partials = _strip_functional_partials(
            grid=grid, rz=rz, wz=wz, slope=slope, inv=inv,
            weights=np.where(engaged, depth, 0.0), step=step,
            wheel_y=wheel_y, wheel_z=wheel_z, rail_y=rail_y, rail_z=rail_z,
            wheel_y_m=wheel_y_m, wheel_z_m=wheel_z_m,
            wheel_roll_rad=wheel_roll_rad,
            lower=lower, upper=upper, d_lower=d_lower, d_upper=d_upper,
            y_c=y_c, effective_modulus_pa=effective_modulus_pa,
            angle_interpolated=abs(grid[int(np.argmax(depth))] - y_c) <= 0.25 * step,
            dz_ds_slope=float(_segment_slope(
                rail_sample.profile.y_m, rail_sample.dz_ds, y_c - rail_y_m)),
        )
    return ContactGeometry(
        y_m=y_c,
        wheel_z_m=wheel_surface,
        rail_z_m=rail_surface,
        penetration_m=penetration,
        normal_y=-slope_at * inv_at,
        normal_z=inv_at,
        tangent_y=inv_at,
        tangent_z=slope_at * inv_at,
        lever_y_m=y_c - wheel_y_m,
        lever_z_m=wheel_surface - wheel_z_m,
        rail_dz_ds=dz_ds,
        # A bounded patch reports the window end as "edge limited" only when the
        # window happens to coincide with the real extent of the overlap.  Once the
        # patch width is a modelling choice, its own boundary is not a geometric edge
        # -- treating it as one is what failed the no_edge_limited gate on every
        # bounded run.
        edge_limited=bool(
            (engaged[0] and lower <= full_lower + 1.0e-12)
            or (engaged[-1] and upper >= full_upper - 1.0e-12)
        ),
        stiffness_n_m_1p5=point_stiffness,
        radius_star_m=radius_star,
        half_width_m=0.5 * engaged_width,
        partials=contact_partials,
    )


def find_spline_contact(
    wheel_profile, rail_sample, *,
    wheel_y_m: float, wheel_z_m: float,
    wheel_roll_rad: float, wheel_lateral_offset_m: float,
    rail_y_m: float, rail_z_m: float,
    effective_modulus_pa: float,
    stiffness_policy: str = "fixed_effective_radius",
    effective_radius_m: float = 0.02,
    ellipticity_correction: float = 1.0,
    point_policy: str = "argmax",
    point_theta_m: float | None = None,
    patch_half_width_m: float | None = None,
    patch_slices: int = 5,
    grid_step_m: float = 0.0,
) -> ContactGeometry | None:
    """Locate the contact with the spline backend, hand the physics to the grid.

    The spline only answers *where* the two surfaces interfere: it resolves a
    curvature discontinuity that a fixed grid can only straddle, which is why the
    dense grid has a first-order error on a kinked section while the spline does not.
    Everything downstream -- normal direction, lever arms, curvature, creep -- is the
    existing assembly, run on a span of a few micrometres around the located point.
    That keeps this policy a geometry backend instead of a second force model, and it
    is why switching the policy cannot silently change the constitutive behaviour.
    """
    from .contact_geometry import fit_segmented, swept_contact

    wheel_y, wheel_z, rail_y, rail_z = _absolute_arrays(
        wheel_profile, rail_sample,
        wheel_y_m=wheel_y_m, wheel_z_m=wheel_z_m,
        wheel_roll_rad=wheel_roll_rad,
        wheel_lateral_offset_m=wheel_lateral_offset_m,
        rail_y_m=rail_y_m, rail_z_m=rail_z_m,
    )
    wheel_band = fit_segmented(wheel_y, wheel_z, name="wheel")
    rail_band = fit_segmented(rail_y, rail_z, name="rail")
    found = swept_contact(
        wheel_band, rail_band,
        wheel_origin_y_m=wheel_y_m + wheel_lateral_offset_m,
        wheel_origin_z_m=wheel_z_m,
        effective_modulus_pa=effective_modulus_pa,
        ellipticity=ellipticity_correction,
    )
    if found is None or found.penetration_m <= 0.0:
        return None
    half = max(2.0 * grid_step_m, 2.0e-6)
    return _contact_on_span(
        wheel_y, wheel_z, rail_sample, rail_y, rail_z,
        wheel_y_m=wheel_y_m, wheel_z_m=wheel_z_m, rail_y_m=rail_y_m,
        lower=found.y_m - half, upper=found.y_m + half,
        patch_half_width_m=patch_half_width_m,
        patch_slices=patch_slices,
        point_policy=point_policy, point_theta_m=point_theta_m,
        stiffness_policy=stiffness_policy,
        effective_modulus_pa=effective_modulus_pa,
        effective_radius_m=effective_radius_m,
        ellipticity_correction=ellipticity_correction,
        geometry_policy="grid",
        grid_step_m=min(grid_step_m, half / 2.0),
    )


def masked_sample_around(
    sample: ProfileSample,
    *,
    center_y_m: float,
    exclusion_m: float,
    drop_m: float = 10.0,
) -> ProfileSample:
    """Copy the sampled rail surface with a deep well where the primary contact sits.

    Two-point contact needs a *second* local extremum of the clearance on the same wheel-rail
    side (L12: the contact-line and conformal two-point algorithms search every local minimum,
    not only the global one).  Rather than write a second searcher, the primary patch is pushed
    ten metres below the wheel and the ordinary search is run again: every policy then works on
    the remaining surface with exactly the same code, so the second point is found, refined and
    given a normal by the same path as the first, and two independent implementations cannot
    drift apart.

    A well (rather than deleting the samples) keeps the abscissa strictly increasing for
    ``np.interp`` and leaves no invented surface spanning the gap: inside the window the depth is
    around -10 m, so no extremum can be reported there.  ``sample`` is returned unchanged when the
    window holds no sample, which is what makes the single-contact cases trivially identical.
    """

    if exclusion_m <= 0.0:
        return sample
    profile = sample.profile
    y = np.asarray(profile.y_m, dtype=float)
    if y.size == 0:
        return sample
    mask = np.abs(y - float(center_y_m)) < exclusion_m
    if not np.any(mask):
        return sample
    z = np.asarray(profile.z_m, dtype=float).copy()
    z[mask] -= float(drop_m)
    return replace(sample, profile=replace(profile, z_m=z))
