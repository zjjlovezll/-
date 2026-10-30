"""Reduced-order wheel/rail contact with explicit applicability boundaries.

The normal elastic exponent and tangential saturation polynomial are adapted from the user's
SDITT MATLAB source. Geometry and damping are independent research implementations and are not
Simpack-equivalent algorithms.

This module is the facade over three split-out siblings: :mod:`velch.contact_models` holds the
dataclasses, :mod:`velch.contact_grid` the station grids, :mod:`velch.contact_search` the
contact-point searches.  What stays here is the dispatch between policies and the force law
built on top of the located contact.  Every name that used to be defined here is re-exported,
so callers keep importing from ``velch.contact``.
"""
from __future__ import annotations

import math

import numpy as np

from .contact_grid import (_RAIL_GRID_CACHE_SIZE, _RAIL_SLOPE_CACHE_SIZE, RAIL_SLOPE_TABLE,
                           _build_rail_grid, _grid_curvature, _grid_slope, _merge_grid,
                           _rail_grid_cache, _rail_node_slopes)
from .contact_law import hunt_crossley_coefficient
from .contact_models import (CURVATURE_POLICIES, DAMPING_POLICIES, GEOMETRY_POLICIES,
                             NORMAL_POLICIES, POINT_POLICIES, STIFFNESS_POLICIES,
                             STRIP_CENTER_POLICIES, ContactGeometry, ContactParameters,
                             ContactPartials, ContactResponse, check_policy,
                             deduplicate_contacts, merge_contact_responses)
from .contact_search import (_absolute_arrays, _contact_on_span, _deepest_depth_y,
                             _segment_slope, _strip_functional_partials, _window_quadratic,
                             find_patch_contact, find_spline_contact, find_strip_contact)
from .profiles import GraphProfile, ProfileError, ProfileSample
from .support_compliance import series_normal_force


# Re-exported so this stays the module callers import from.  Listed explicitly (not ``*``) so a
# name disappearing from a sibling is a hard ImportError here instead of a silent runtime miss.
__all__ = [
    "CURVATURE_POLICIES", "DAMPING_POLICIES", "GEOMETRY_POLICIES", "NORMAL_POLICIES",
    "POINT_POLICIES", "STIFFNESS_POLICIES", "STRIP_CENTER_POLICIES",
    "ContactGeometry", "ContactParameters", "ContactPartials", "ContactResponse",
    "deduplicate_contacts", "merge_contact_responses",
    "find_patch_contact", "find_spline_contact", "find_strip_contact",
    "find_graph_contact", "find_graph_contacts", "evaluate_contact", "saturate_creep_force",
    "hunt_crossley_coefficient", "series_normal_force",
]


def _single_valued_envelope(wheel_y: np.ndarray, wheel_z: np.ndarray):
    """Return the wheel envelope as a strictly increasing function of lateral position.

    A rolled wheel maps its own height into ``y`` (``-sin(roll) * z``), so a steep stretch of the
    profile — the flange, typically — folds the curve over itself.  The contact search only needs
    "at this lateral position, how high is the wheel", which is the lower of the folded branches, so
    sort by ``y`` and keep the lowest point per distinct ``y``.  With roll = 0 the input is already
    increasing and this returns it unchanged.
    """

    if wheel_y.size < 2 or bool(np.all(wheel_y[1:] > wheel_y[:-1])):
        return wheel_y, wheel_z
    order = np.argsort(wheel_y, kind="stable")
    ys = wheel_y[order]
    zs = wheel_z[order]
    starts = np.flatnonzero(np.r_[True, ys[1:] != ys[:-1]])
    return ys[starts], np.minimum.reduceat(zs, starts)


def find_graph_contact(
    wheel_profile: GraphProfile,
    rail_sample: ProfileSample,
    *,
    wheel_y_m: float,
    wheel_z_m: float,
    wheel_roll_rad: float,
    wheel_lateral_offset_m: float,
    rail_y_m: float,
    rail_z_m: float,
    search_half_width_m: float | None = None,
    previous_y_m: float | None = None,
    patch_half_width_m: float = 0.0,
    patch_slices: int = 5,
    point_policy: str = "argmax",
    point_theta_m: float | None = None,
    stiffness_policy: str = "local_circular",
    effective_modulus_pa: float | None = None,
    effective_radius_m: float | None = None,
    ellipticity_correction: float = 1.0,
    geometry_policy: str = "grid",
    patch_window_m: float = 1.0e-3,
    grid_step_m: float = 0.0,
    normal_policy: str = "point_hertz",
    strip_dy_m: float = 2.5e-4,
    strip_min_depth_m: float = 0.0,
    strip_half_width_m: float | None = None,
    strip_center_policy: str = "deepest",
    curvature_policy: str = "window",
    surface_key: tuple[str, ...] | None = None,
    partials: bool = False,
) -> ContactGeometry | None:
    """Find one maximum-penetration candidate on a wheel/rail graph pair.

    A vertical graph comparison approximates the local normal gap. It covers
    a single contact per rail patch, including multiple simultaneous rails.
    It is not suitable for undercuts or a multivalued flange contact surface.

    ``previous_y_m`` and ``search_half_width_m`` enable a bounded local search
    around the last accepted contact point, the same structure the vendor model
    exposes as its contact search window. The local pass is only accepted when
    it finds a strictly interior point with positive penetration; any edge hit
    or loss of contact falls back to the exhaustive span, so the local search
    can narrow the work but not silently move the contact.

    ``patch_half_width_m`` replaces the point interpenetration by the Hertzian
    equivalent of a contact patch of that half-width: the reported penetration
    is ``(mean over slices of depth**1.5)**(2/3)``. On a smooth surface the
    slices agree and nothing changes; across a rail step it keeps a decaying
    normal force instead of dropping to zero, which is how a discretised
    elastic contact (vendor ``cont_disc_delta``) behaves.
    """
    local_y = wheel_lateral_offset_m + wheel_profile.y_m
    local_z = wheel_profile.z_m
    c, s = math.cos(wheel_roll_rad), math.sin(wheel_roll_rad)
    wheel_y = wheel_y_m + c * local_y - s * local_z
    wheel_z = wheel_z_m + s * local_y + c * local_z
    wheel_y, wheel_z = _single_valued_envelope(wheel_y, wheel_z)
    rail_y = rail_y_m + rail_sample.profile.y_m
    rail_z = rail_z_m + rail_sample.profile.z_m
    if geometry_policy not in GEOMETRY_POLICIES:
        raise ValueError(f"unknown geometry policy {geometry_policy!r}")
    if normal_policy not in NORMAL_POLICIES:
        raise ValueError(f"unknown normal policy {normal_policy!r}")
    if normal_policy == "strip_integral":
        center_y = None
        if strip_half_width_m is not None:
            # Bounded patch.  Follow the running contact when a seed exists (that is
            # the vendor ``cont_searchdeltay`` behaviour: the patch may not jump
            # laterally), otherwise bootstrap from the deepest point.
            center_y = previous_y_m
            if center_y is None:
                if strip_center_policy == "reference":
                    # The rail reference plane is the crown datum by construction:
                    # the case's rail offset places local y = 0 on the running
                    # surface, so this centres the patch on the crown.
                    center_y = rail_y_m
                else:
                    center_y = _deepest_depth_y(
                        wheel_profile, rail_sample,
                        wheel_y_m=wheel_y_m, wheel_z_m=wheel_z_m,
                        wheel_roll_rad=wheel_roll_rad,
                        wheel_lateral_offset_m=wheel_lateral_offset_m,
                        rail_y_m=rail_y_m, rail_z_m=rail_z_m,
                        step_m=max(4.0 * strip_dy_m, 2.0e-4),
                    )
            if center_y is None:
                return None
        return find_strip_contact(
            wheel_profile, rail_sample,
            wheel_y_m=wheel_y_m, wheel_z_m=wheel_z_m,
            wheel_roll_rad=wheel_roll_rad,
            wheel_lateral_offset_m=wheel_lateral_offset_m,
            rail_y_m=rail_y_m, rail_z_m=rail_z_m,
            strip_dy_m=strip_dy_m, strip_min_depth_m=strip_min_depth_m,
            center_y_m=center_y, half_width_m=strip_half_width_m,
            clip_to_engaged_run=strip_center_policy == "run",
            effective_modulus_pa=effective_modulus_pa,
            effective_radius_m=effective_radius_m,
            ellipticity_correction=ellipticity_correction,
            stiffness_policy=stiffness_policy,
            curvature_policy=curvature_policy,
            geometry_policy=geometry_policy,
            grid_step_m=grid_step_m,
            surface_key=surface_key,
            partials=partials,
        )
    if geometry_policy == "patch":
        return find_patch_contact(
            wheel_profile, rail_sample,
            wheel_y_m=wheel_y_m, wheel_z_m=wheel_z_m,
            wheel_roll_rad=wheel_roll_rad,
            wheel_lateral_offset_m=wheel_lateral_offset_m,
            rail_y_m=rail_y_m, rail_z_m=rail_z_m,
            window_m=patch_window_m,
            effective_modulus_pa=(effective_modulus_pa
                                  if stiffness_policy == "local_circular" else None),
            effective_radius_m=effective_radius_m,
            ellipticity_correction=ellipticity_correction,
        )
    if geometry_policy == "spline":
        return find_spline_contact(
            wheel_profile, rail_sample,
            wheel_y_m=wheel_y_m, wheel_z_m=wheel_z_m,
            wheel_roll_rad=wheel_roll_rad,
            wheel_lateral_offset_m=wheel_lateral_offset_m,
            rail_y_m=rail_y_m, rail_z_m=rail_z_m,
            effective_modulus_pa=effective_modulus_pa,
            stiffness_policy=stiffness_policy,
            effective_radius_m=effective_radius_m,
            ellipticity_correction=ellipticity_correction,
            point_policy=point_policy, point_theta_m=point_theta_m,
            patch_half_width_m=patch_half_width_m,
            patch_slices=patch_slices,
            grid_step_m=grid_step_m,
        )
    lower, upper = max(wheel_y[0], rail_y[0]), min(wheel_y[-1], rail_y[-1])
    if upper <= lower:
        return None
    if search_half_width_m is not None and previous_y_m is not None:
        lo = max(lower, previous_y_m - search_half_width_m)
        hi = min(upper, previous_y_m + search_half_width_m)
        if hi > lo:
            local = _contact_on_span(wheel_y, wheel_z, rail_sample, rail_y, rail_z,
                                     wheel_y_m=wheel_y_m, wheel_z_m=wheel_z_m,
                                     rail_y_m=rail_y_m, lower=lo, upper=hi,
                                     patch_half_width_m=patch_half_width_m,
                                     patch_slices=patch_slices,
                                     point_policy=point_policy, point_theta_m=point_theta_m,
                                     stiffness_policy=stiffness_policy,
                                     effective_modulus_pa=effective_modulus_pa,
                                     effective_radius_m=effective_radius_m,
                                     ellipticity_correction=ellipticity_correction,
                                     geometry_policy=geometry_policy,
                                     grid_step_m=grid_step_m)
            if local is not None and local.penetration_m > 0.0 and not local.edge_limited:
                return local
    return _contact_on_span(wheel_y, wheel_z, rail_sample, rail_y, rail_z,
                            wheel_y_m=wheel_y_m, wheel_z_m=wheel_z_m,
                            rail_y_m=rail_y_m, lower=lower, upper=upper,
                            patch_half_width_m=patch_half_width_m,
                            patch_slices=patch_slices,
                            point_policy=point_policy, point_theta_m=point_theta_m,
                            stiffness_policy=stiffness_policy,
                            effective_modulus_pa=effective_modulus_pa,
                            effective_radius_m=effective_radius_m,
                            ellipticity_correction=ellipticity_correction,
                            geometry_policy=geometry_policy,
                            grid_step_m=grid_step_m)


def saturate_creep_force(linear_x_n: float, linear_lateral_n: float,
                         mu: float, normal_force_n: float) -> tuple[float, float]:
    """SDITT-style cubic force saturation with an exact zero-creep branch.

    The old MATLAB path divides Pzz by Pz even when both are zero. This
    implementation returns zero exactly at zero linear creep demand.
    """
    demand = math.hypot(linear_x_n, linear_lateral_n)
    limit = mu * normal_force_n
    if demand <= 0.0 or limit <= 0.0:
        return 0.0, 0.0
    if demand <= 3.0 * limit:
        ratio = demand / limit
        magnitude = limit * (ratio - ratio * ratio / 3.0 + ratio ** 3 / 27.0)
    else:
        magnitude = limit
    scale = magnitude / demand
    return linear_x_n * scale, linear_lateral_n * scale


def evaluate_contact(
    geometry: ContactGeometry | None,
    law: ContactParameters,
    *,
    wheel_v_y_m_s: float,
    wheel_v_z_m_s: float,
    wheel_roll_rate_rad_s: float,
    wheel_spin_rate_rad_s: float,
    rail_v_y_m_s: float,
    rail_v_z_m_s: float,
    travel_speed_m_s: float,
    creep_attack_velocity_m_s: float = 0.0,
    support_compliance_m_per_n: float | None = None,
    curvature_1_per_m: float = 0.0,
) -> ContactResponse:
    if geometry is None or geometry.penetration_m <= 0:
        return ContactResponse(False, geometry)
    g = geometry
    wheel_contact_v_y = wheel_v_y_m_s - wheel_roll_rate_rad_s * g.lever_z_m
    wheel_contact_v_z = wheel_v_z_m_s + wheel_roll_rate_rad_s * g.lever_y_m
    rel_y = wheel_contact_v_y - rail_v_y_m_s
    rel_z = wheel_contact_v_z - rail_v_z_m_s
    approach = -(rel_y * g.normal_y + rel_z * g.normal_z)
    # The prescribed x motion changes the profile elevation at the contact.
    approach += travel_speed_m_s * g.rail_dz_ds * g.normal_z
    slip_lateral = rel_y * g.tangent_y + rel_z * g.tangent_z + creep_attack_velocity_m_s
    # On a curve the two contact points of a wheelset travel different arc lengths: the point at
    # lateral offset ``b`` from the axle centre moves at ``v (1 + kappa b)`` when the centre of the
    # curve is on the -y side (the code's convention, where +y is the outer rail).  Without this
    # term the longitudinal creep carries no curvature at all, so a wheelset asked to run a 350 m
    # curve sees no rolling-radius difference to steer with and rides up the flange instead -- the
    # failure was `graph slope limit at axle1_left/left` ten metres into the run.
    slip_x = (travel_speed_m_s + wheel_spin_rate_rad_s * g.lever_z_m
              - curvature_1_per_m * travel_speed_m_s * g.lever_y_m)
    depth = g.penetration_m
    stiffness = g.stiffness_n_m_1p5
    if stiffness is None:
        stiffness = law.normal_stiffness_n_m_1p5
    elastic = series_normal_force(depth, stiffness, support_compliance_m_per_n)
    if stiffness > 0.0:
        hertz_penetration = (elastic / stiffness) ** (2.0 / 3.0)
    else:
        hertz_penetration = 0.0
    settlement = elastic * support_compliance_m_per_n if support_compliance_m_per_n else 0.0
    if law.damping_policy == "hunt_crossley":
        coefficient = hunt_crossley_coefficient(stiffness, law.restitution_coefficient,
                                                law.damping_reference_speed_m_s)
        damping = coefficient * depth ** 1.5 * approach
    else:
        damping = law.normal_damping_n_s_m_1p5 * math.sqrt(depth) * approach
    if law.damping_force_cap_ratio is not None:
        # A contact cannot dissipate more than it stores per cycle. Without this the
        # sqrt(delta)*v term turns every sharp geometry step into a force spike: at the
        # switch panel a 170 um sample produced 150 kN of damping on top of 250 kN elastic.
        cap = law.damping_force_cap_ratio * abs(elastic)
        damping = math.copysign(min(abs(damping), cap), damping)
    normal = max(0.0, elastic + damping)
    reference_speed = max(abs(travel_speed_m_s), law.reference_speed_floor_m_s)
    stiffness_x = law.creep_stiffness_x_n
    stiffness_lateral = law.creep_stiffness_lateral_n
    if law.creep_stiffness_from_patch:
        # Kalker's linear theory puts the creep coefficients on the contact ellipse:
        # f11 = 2 E* a b C11 and f22 = 2 E* a b C22, with a the semi-axis along rolling and b the
        # lateral one.  `half_width_m` is the lateral semi-axis the contact search already
        # measured, and a comes from the circular-equivalent Hertz relation at the same load, so
        # the pair is consistent with the normal force actually being carried.  The shape
        # factors are Kalker's circular values (nu = 0.3): C11 = 0.98, C22 = 0.99.  Ellipticity
        # dependence of C11/C22 is NOT included yet, and there is still no spin term.
        modulus = law.effective_modulus_pa
        radius = g.radius_star_m if g.radius_star_m > 0.0 else law.effective_radius_m
        if modulus > 0.0 and radius > 0.0 and g.half_width_m > 0.0 and normal > 0.0:
            half_a = (3.0 * normal * radius / (4.0 * modulus)) ** (1.0 / 3.0)
            half_b = g.half_width_m
            area = math.pi * half_a * half_b
            stiffness_x = 2.0 * modulus * area / math.pi * law.creep_shape_x
            stiffness_lateral = 2.0 * modulus * area / math.pi * law.creep_shape_lateral
    linear_x = -stiffness_x * slip_x / reference_speed
    linear_lateral = -stiffness_lateral * slip_lateral / reference_speed
    force_x, force_t = saturate_creep_force(linear_x, linear_lateral,
                                            law.friction_coefficient, normal)
    force_y = normal * g.normal_y + force_t * g.tangent_y
    force_z = normal * g.normal_z + force_t * g.tangent_z
    return ContactResponse(
        active=normal > 0.0, geometry=g,
        normal_force_n=normal, normal_elastic_n=elastic, normal_damping_n=normal - elastic,
        longitudinal_force_n=force_x, lateral_tangent_force_n=force_t,
        wheel_force_y_n=force_y, wheel_force_z_n=force_z,
        wheel_roll_moment_nm=g.lever_y_m * force_z - g.lever_z_m * force_y,
        wheel_spin_moment_nm=g.lever_z_m * force_x,
        normal_approach_speed_m_s=approach, slip_x_m_s=slip_x, slip_lateral_m_s=slip_lateral,
        friction_dissipation_w=max(0.0, -(force_x * slip_x + force_t * slip_lateral)),
        damping_dissipation_w=max(0.0, (normal - elastic) * approach),
        hertz_penetration_m=hertz_penetration, support_settlement_m=settlement,
    )


def find_graph_contacts(
    wheel_profile: GraphProfile,
    rail_sample: ProfileSample,
    *,
    wheel_y_m: float,
    wheel_z_m: float,
    wheel_roll_rad: float,
    wheel_lateral_offset_m: float,
    rail_y_m: float,
    rail_z_m: float,
    maximum_contacts: int = 3,
    minimum_separation_m: float = 0.004,
) -> tuple[ContactGeometry, ...]:
    """Return every local maximum of the vertical graph gap on one rail patch.

    A turnout cross-section merges the stock, switch and wing rail heads into a
    single z(y) polyline, so the depth surface carries several local maxima. The
    single-contact search keeps only the deepest one and jumps between rail heads;
    this search keeps one contact per lobe so each rail head carries its own load.
    Lobes closer than ``minimum_separation_m`` are treated as one contact.
    """
    local_y = wheel_lateral_offset_m + wheel_profile.y_m
    local_z = wheel_profile.z_m
    c, s = math.cos(wheel_roll_rad), math.sin(wheel_roll_rad)
    wheel_y = wheel_y_m + c * local_y - s * local_z
    wheel_z = wheel_z_m + s * local_y + c * local_z
    wheel_y, wheel_z = _single_valued_envelope(wheel_y, wheel_z)
    rail_y = rail_y_m + rail_sample.profile.y_m
    rail_z = rail_z_m + rail_sample.profile.z_m
    lower, upper = max(wheel_y[0], rail_y[0]), min(wheel_y[-1], rail_y[-1])
    if upper <= lower:
        return ()
    grid = _merge_grid(wheel_y, rail_y, lower, upper)
    if grid.size < 3:
        return ()
    w_z = np.interp(grid, wheel_y, wheel_z)
    r_z = np.interp(grid, rail_y, rail_z)
    slopes = _grid_slope(r_z, grid)
    inv_lengths = 1.0 / np.sqrt(1.0 + slopes * slopes)
    depth = (r_z - w_z) * inv_lengths
    inner = depth[1:-1]
    peaks = np.flatnonzero((inner >= depth[:-2]) & (inner > depth[2:])) + 1
    candidates = [int(i) for i in peaks if depth[i] > 0.0]
    if not candidates:
        return ()
    candidates.sort(key=lambda i: -depth[i])
    chosen: list[int] = []
    for i in candidates:
        if all(abs(grid[i] - grid[j]) >= minimum_separation_m for j in chosen):
            chosen.append(i)
        if len(chosen) >= maximum_contacts:
            break
    chosen.sort(key=lambda i: grid[i])
    out = []
    for i in chosen:
        y = float(grid[i])
        slope = float(slopes[i])
        inv = float(inv_lengths[i])
        dz_ds = float(np.interp(y - rail_y_m, rail_sample.profile.y_m, rail_sample.dz_ds))
        out.append(ContactGeometry(
            y_m=y,
            wheel_z_m=float(w_z[i]),
            rail_z_m=float(r_z[i]),
            penetration_m=float(depth[i]),
            normal_y=-slope * inv,
            normal_z=inv,
            tangent_y=inv,
            tangent_z=slope * inv,
            lever_y_m=y - wheel_y_m,
            lever_z_m=float(w_z[i]) - wheel_z_m,
            rail_dz_ds=dz_ds,
            edge_limited=i == 0 or i == grid.size - 1,
        ))
    return tuple(out)
