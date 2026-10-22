"""Reduced-order wheel/rail contact with explicit applicability boundaries.

The normal elastic exponent and tangential saturation polynomial are adapted
from the user's SDITT MATLAB source. Geometry and damping are independent
research implementations and are not Simpack-equivalent algorithms.
"""
from __future__ import annotations

import math
import os
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np

from .contact_law import (DAMPING_POLICIES, POINT_POLICIES, STIFFNESS_POLICIES,
                          adaptive_theta_m, check_policy, circular_equivalent_radius,
                          hertz_half_width_m, hertz_stiffness_n_m_1p5,
                          hunt_crossley_coefficient, local_curvature,
                          quadratic_fit, soft_argmax_position)
from .profiles import GraphProfile, ProfileError, ProfileSample

GEOMETRY_POLICIES = ("grid", "patch", "fixed_grid", "cached_grid", "spline")
"""How the contact point is located.

``grid`` samples both surfaces on a merged grid and takes the deepest node: the
historical path, kept bit-exact so every existing case keeps reproducing.
``patch`` refines the bracket with patch-scale quadratics and solves the
clearance extremum analytically, which removes the node-to-node sliding of the
contact point (see :func:`find_patch_contact`).
"""

from .support_compliance import series_normal_force

CURVATURE_POLICIES = ("window", "grid_stencil")
"""How the contact-scale curvature is estimated.

``window`` fits a least-squares quadratic over ±half_span about the contact point
(two window fits per patch, about 50 µs of a 108 µs geometry call).
``grid_stencil`` reuses the merged grid the search already built and takes the
second difference of both surfaces on it: no extra passes, no fancy indexing, and
the smoothing length becomes one grid step instead of the ±1 mm window. It is a
different estimator, so it is a policy and not the default — switching it moves
the static penetration a few per cent, which the frozen oracle would notice.
"""

NORMAL_POLICIES = ("point_hertz", "strip_integral")
STRIP_CENTER_POLICIES = ("deepest", "reference", "run")
"""How the normal force is built.

``point_hertz`` applies ``N = C δ^1.5`` at a single deepest point: one spring,
which rings at the wheelset's own contact resonance as soon as the geometry
excites it.
``strip_integral`` integrates a per-unit-width Hertzian line stiffness over every
engaged strip ``N = (π/4) E* Σ max(δ,0) Δy``. Neighbouring strips keep carrying
load while the deepest one unloads, so the force cannot fall to zero on a
20 mm-wide notch — the mechanism the vendor exposes as discrete-elastic contact
(``rw.cont.meth = 2``, ``cont_disc_delta = 5e-4``).
"""


@dataclass(frozen=True)
class ContactParameters:
    normal_model: str
    damping_model: str
    tangential_model: str
    effective_modulus_pa: float
    effective_radius_m: float
    normal_damping_n_s_m_1p5: float
    friction_coefficient: float
    creep_stiffness_x_n: float
    creep_stiffness_lateral_n: float
    reference_speed_floor_m_s: float
    patch_half_width_m: float = 0.0
    patch_slices: int = 5
    point_policy: str = "argmax"
    point_theta_m: float | None = None
    stiffness_policy: str = "fixed_effective_radius"
    ellipticity_correction: float = 1.0
    wheel_rolling_radius_m: float = 0.43
    damping_policy: str = "fixed_coefficient"
    restitution_coefficient: float = 0.5
    damping_reference_speed_m_s: float = 0.5
    damping_force_cap_ratio: float | None = None
    duplicate_patch_window_m: float = 0.0
    geometry_policy: str = "grid"
    patch_window_m: float = 1.0e-3
    grid_step_m: float = 0.0
    normal_policy: str = "point_hertz"
    strip_dy_m: float = 2.5e-4
    strip_min_depth_m: float = 0.0
    strip_half_width_m: float | None = None
    strip_center_policy: str = "deepest"
    curvature_policy: str = "window"

    def __post_init__(self) -> None:
        if self.normal_model != "hertz_effective_radius":
            raise ValueError("only hertz_effective_radius normal model is implemented")
        if self.damping_model != "delta_half_velocity":
            raise ValueError("only delta_half_velocity damping is implemented")
        if self.tangential_model != "sditt_cubic_saturation":
            raise ValueError("only sditt_cubic_saturation tangential model is implemented")
        positive = (self.effective_modulus_pa, self.effective_radius_m, self.reference_speed_floor_m_s)
        nonnegative = (self.normal_damping_n_s_m_1p5, self.friction_coefficient,
                       self.creep_stiffness_x_n, self.creep_stiffness_lateral_n)
        if any(not math.isfinite(x) or x <= 0 for x in positive):
            raise ValueError("effective modulus, radius, and speed floor must be positive finite SI values")
        if any(not math.isfinite(x) or x < 0 for x in nonnegative):
            raise ValueError("damping, friction, and creep stiffness must be nonnegative finite SI values")
        if not math.isfinite(self.patch_half_width_m) or self.patch_half_width_m < 0.0:
            raise ValueError("patch_half_width_m must be nonnegative and finite")
        if not math.isfinite(self.duplicate_patch_window_m) or self.duplicate_patch_window_m < 0.0:
            raise ValueError("duplicate_patch_window_m must be nonnegative and finite")
        if self.geometry_policy not in GEOMETRY_POLICIES:
            raise ValueError(f"geometry_policy must be one of {GEOMETRY_POLICIES}")
        if not math.isfinite(self.patch_window_m) or self.patch_window_m <= 0.0:
            raise ValueError("patch_window_m must be positive and finite")
        if not math.isfinite(self.grid_step_m) or self.grid_step_m < 0.0:
            raise ValueError("grid_step_m must be nonnegative and finite")
        if self.normal_policy not in NORMAL_POLICIES:
            raise ValueError(f"normal_policy must be one of {NORMAL_POLICIES}")
        if not math.isfinite(self.strip_dy_m) or self.strip_dy_m <= 0.0:
            raise ValueError("strip_dy_m must be positive and finite")
        if not math.isfinite(self.strip_min_depth_m) or self.strip_min_depth_m < 0.0:
            raise ValueError("strip_min_depth_m must be nonnegative and finite")
        if self.strip_half_width_m is not None:
            # Bounded lateral strip: the patch is integrated around the deepest point
            # instead of over the whole wheel/rail overlap.  The whole-overlap form
            # swallows flangeway recesses and relief grooves, which is how a 24 mm
            # deep seat cut ends up on the running surface (see the 596 kN history).
            if not math.isfinite(self.strip_half_width_m) or self.strip_half_width_m <= 0.0:
                raise ValueError("strip_half_width_m must be positive and finite")
        if self.strip_center_policy not in STRIP_CENTER_POLICIES:
            raise ValueError(f"strip_center_policy must be one of {STRIP_CENTER_POLICIES}")
        if not isinstance(self.patch_slices, int) or self.patch_slices < 3 or self.patch_slices % 2 == 0:
            raise ValueError("patch_slices must be an odd integer >= 3")
        check_policy(self.point_policy, POINT_POLICIES, "contact point")
        check_policy(self.stiffness_policy, STIFFNESS_POLICIES, "contact stiffness")
        check_policy(self.damping_policy, DAMPING_POLICIES, "contact damping")
        check_policy(self.curvature_policy, CURVATURE_POLICIES, "contact curvature")
        if self.point_theta_m is not None:
            if not math.isfinite(self.point_theta_m) or self.point_theta_m <= 0.0:
                raise ValueError("point_theta_m must be a positive finite length")
        if not math.isfinite(self.ellipticity_correction) or self.ellipticity_correction <= 0.0:
            raise ValueError("ellipticity_correction must be positive and finite")
        if not math.isfinite(self.wheel_rolling_radius_m) or self.wheel_rolling_radius_m <= 0.0:
            raise ValueError("wheel_rolling_radius_m must be positive and finite")
        if not 0.0 <= self.restitution_coefficient < 1.0:
            raise ValueError("restitution_coefficient must be in [0, 1)")
        if not math.isfinite(self.damping_reference_speed_m_s) or self.damping_reference_speed_m_s <= 0.0:
            raise ValueError("damping_reference_speed_m_s must be positive and finite")
        if self.damping_force_cap_ratio is not None:
            if not math.isfinite(self.damping_force_cap_ratio) or self.damping_force_cap_ratio <= 0.0:
                raise ValueError("damping_force_cap_ratio must be positive and finite when set")

    @property
    def patch_enabled(self) -> bool:
        return self.patch_half_width_m > 0.0

    @property
    def normal_stiffness_n_m_1p5(self) -> float:
        # Hertz sphere/half-space effective-radius simplification. This is a
        # configurable reduced-order stiffness, not the legacy STRIPES law.
        return 4.0 / 3.0 * self.effective_modulus_pa * math.sqrt(self.effective_radius_m)


#: Order of the five rigid contact modes used by :class:`ContactPartials`.
CONTACT_MODES: tuple[str, ...] = ("wheel_y", "wheel_z", "wheel_roll", "rail_y", "rail_z")


@dataclass(frozen=True)
class ContactPartials:
    """Gradients of the strip contact map w.r.t. the five rigid contact modes.

    A strip contact is *not* a point contact, and the frozen-angle lever-arm
    Jacobian of a point contact is the wrong linearisation of it twice over:

    * the normal force is a functional of the whole depth field,
      ``N = (pi/4) E* sum_engaged depth_i * step``, so ``dN/dq`` is the band
      average of the depth gradient -- about 6 % smaller than the deepest
      strip's own gradient here -- and
    * the contact centroid moves with the wheelset, which drags the lever arms
      with it; ``dlever_y/dq`` is O(1) and multiplies the normal force directly.

    Both drop out of the point-contact form, which is why the analytic-Jacobian
    gate found a uniform 4..7 % error on exactly the wheelset ``y``/``z``/``roll``
    and rail ``y``/``z`` columns. ``normal_force_n`` is the elastic force
    gradient; the total force gradient rescales it by the damping branch, exactly
    as ``dN/ddelta`` composes with ``d(delta)/dq``.
    """

    normal_force_n: tuple[float, ...] = ()
    lever_y_m: tuple[float, ...] = ()
    lever_z_m: tuple[float, ...] = ()
    #: ``d(slope at the contact)/dq``: the normal direction rotates as the contact
    #: walks along a curved part of the profile. Zero on a flat crown, which is why
    #: it hides at the flange-free stations.
    normal_slope: tuple[float, ...] = ()
    #: ``d(rail_dz_ds)/dq``, the longitudinal elevation gradient read at the contact.
    #: It feeds the approach speed through ``travel_speed * dz_ds * normal_z``, so on
    #: a station with a non-zero grade it is the whole damping channel's q-dependence.
    rail_dz_ds: tuple[float, ...] = ()


@dataclass(frozen=True)
class ContactGeometry:
    y_m: float
    wheel_z_m: float
    rail_z_m: float
    penetration_m: float
    normal_y: float
    normal_z: float
    tangent_y: float
    tangent_z: float
    lever_y_m: float
    lever_z_m: float
    rail_dz_ds: float
    edge_limited: bool = False
    stiffness_n_m_1p5: float | None = None
    radius_star_m: float = 0.0
    half_width_m: float = 0.0
    #: Only assembled on request (the analytic Jacobian asks for it); the solver's
    #: default path leaves it ``None`` so the physics and the cost are unchanged.
    partials: ContactPartials | None = None


@dataclass(frozen=True)
class ContactResponse:
    active: bool
    geometry: ContactGeometry | None
    normal_force_n: float = 0.0
    normal_elastic_n: float = 0.0
    normal_damping_n: float = 0.0
    longitudinal_force_n: float = 0.0
    lateral_tangent_force_n: float = 0.0
    wheel_force_y_n: float = 0.0
    wheel_force_z_n: float = 0.0
    wheel_roll_moment_nm: float = 0.0
    wheel_spin_moment_nm: float = 0.0
    normal_approach_speed_m_s: float = 0.0
    slip_x_m_s: float = 0.0
    slip_lateral_m_s: float = 0.0
    friction_dissipation_w: float = 0.0
    damping_dissipation_w: float = 0.0
    # S1-e: the reported depth is the total approach; these split it into the
    # Hertzian indentation of the contact spring and the rail settling on its
    # fasteners. Without a support compliance the settlement is zero and the
    # Hertz part equals the depth, which is the pre-S1-e meaning.
    hertz_penetration_m: float = 0.0
    support_settlement_m: float = 0.0

def merge_contact_responses(responses) -> "ContactResponse":
    """Sum several simultaneous contacts of one wheel on one track side.

    A turnout cross-section has more than one rail body per side; each body gets
    its own contact. The wheel force is the sum of them, while the reported
    geometry is the deepest one (that is the point a reader should see).
    """
    active = [item for item in responses if item.active and item.geometry is not None]
    if not active:
        return ContactResponse(False, None)
    deepest = max(active, key=lambda item: item.geometry.penetration_m)
    return ContactResponse(
        True,
        deepest.geometry,
        normal_force_n=sum(item.normal_force_n for item in active),
        normal_elastic_n=sum(item.normal_elastic_n for item in active),
        normal_damping_n=sum(item.normal_damping_n for item in active),
        longitudinal_force_n=sum(item.longitudinal_force_n for item in active),
        lateral_tangent_force_n=sum(item.lateral_tangent_force_n for item in active),
        wheel_force_y_n=sum(item.wheel_force_y_n for item in active),
        wheel_force_z_n=sum(item.wheel_force_z_n for item in active),
        wheel_roll_moment_nm=sum(item.wheel_roll_moment_nm for item in active),
        wheel_spin_moment_nm=sum(item.wheel_spin_moment_nm for item in active),
        normal_approach_speed_m_s=deepest.normal_approach_speed_m_s,
        slip_x_m_s=deepest.slip_x_m_s,
        slip_lateral_m_s=deepest.slip_lateral_m_s,
        friction_dissipation_w=sum(item.friction_dissipation_w for item in active),
        damping_dissipation_w=sum(item.damping_dissipation_w for item in active),
        hertz_penetration_m=deepest.hertz_penetration_m,
        support_settlement_m=deepest.support_settlement_m,
    )


def deduplicate_contacts(entries, window_m: float):
    """Drop overlapping contact patches of one wheel on one track side.

    Two rail bodies are separate surfaces, but when the wheel touches both
    within one footprint the deeper contact already accounts for the shared
    Hertzian area; summing a second full patch there double counts the load
    (the SDITT overlap trimming problem). Contacts further apart than
    ``window_m`` stay independent, which is the normal turnout case where the
    wing rail and the point rail sit 30-40 mm apart.

    ``entries`` is a sequence of ``(body_id, geometry, response)`` in body
    order; inactive entries pass through untouched so callers keep one record
    per body.
    """
    if window_m <= 0.0:
        return list(entries)
    active = [item for item in entries if item[1] is not None and item[2].active]
    idle = [item for item in entries if not (item[1] is not None and item[2].active)]
    accepted: list = []
    for item in sorted(active, key=lambda entry: entry[1].penetration_m, reverse=True):
        if any(abs(item[1].y_m - other[1].y_m) < window_m for other in accepted):
            continue
        accepted.append(item)
    return accepted + idle



_RAIL_GRID_CACHE_SIZE = 192
"""How many station grids to keep.

The run walks the profile monotonically, so a small window is enough and it keeps the
cache at a couple of megabytes instead of growing with the number of stations.
"""

_rail_grid_cache: "OrderedDict[tuple[int, float, float], tuple[np.ndarray, np.ndarray, np.ndarray, float]]" = OrderedDict()


def _build_rail_grid(rail_y: np.ndarray, rail_z: np.ndarray, rail_sample: ProfileSample,
                     grid_step_m: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Rail surface, and its slope, on a station-independent uniform axis.

    The rail geometry at a station is fixed while the wheelset moves through it, yet
    the merged-grid path re-interpolates it on every contact call -- once for the
    rail and once for the wheel, plus a sort of both node sets. Hoisting the rail
    half out of the call leaves one interpolation (the wheel) and one argmax.

    The axis spans the rail profile itself, so it does not depend on where the wheel
    currently is; each call slices the part that overlaps the wheel.
    """

    node = rail_sample.profile.y_m
    low = float(node[0])
    high = float(node[-1])
    span = high - low
    step = (grid_step_m if grid_step_m > 0.0 else max(2.5e-5, min(5.0e-4, span / 512.0)))
    count = max(2, int(math.floor(span / step)) + 1)
    step = span / (count - 1)
    axis = low + step * np.arange(count, dtype=float)
    axis_z = np.interp(axis, rail_y, rail_z)
    axis_slope = _grid_slope(axis_z, axis)
    return axis, axis_z, axis_slope, step


def _merge_grid(wheel_y: np.ndarray, rail_y: np.ndarray, lower: float, upper: float) -> np.ndarray:
    """Sorted union of the two lateral grids inside [lower, upper].

    Identical values to ``np.unique(np.concatenate(...))`` but without the
    hashing path: both sources are already increasing, so a sort plus an
    adjacency mask reproduces the same ascending, duplicate-free array.
    """
    parts = [np.array([lower, upper])]
    inside = wheel_y[(wheel_y > lower) & (wheel_y < upper)]
    if inside.size:
        parts.append(inside)
    inside = rail_y[(rail_y > lower) & (rail_y < upper)]
    if inside.size:
        parts.append(inside)
    merged = np.sort(np.concatenate(parts)) if len(parts) > 1 else parts[0]
    if merged.size > 1:
        keep = np.empty(merged.size, dtype=bool)
        keep[0] = True
        keep[1:] = merged[1:] != merged[:-1]
        merged = merged[keep]
    return merged


def _grid_slope(z: np.ndarray, x: np.ndarray) -> np.ndarray:
    """``np.gradient(z, x, edge_order=1)`` written out for the hot path."""
    n = z.size
    slope = np.empty(n, dtype=float)
    if n == 2:
        slope[0] = slope[1] = (z[1] - z[0]) / (x[1] - x[0])
        return slope
    slope[0] = (z[1] - z[0]) / (x[1] - x[0])
    slope[-1] = (z[-1] - z[-2]) / (x[-1] - x[-2])
    slope[1:-1] = (z[2:] - z[:-2]) / (x[2:] - x[:-2])
    return slope


def _grid_curvature(z: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Second derivative of ``z(x)`` on the merged grid, for the ``grid_stencil`` policy.

    Two extra vectorised passes over arrays the search already holds, in place of
    two least-squares window fits over the raw node lists (about 50 µs of a
    108 µs geometry call). Same meaning as ``2 * quadratic[0]`` from
    :func:`_window_quadratic`, different smoothing length: one grid step here,
    the ±half_span window there.
    """
    n = z.size
    curvature = np.empty(n, dtype=float)
    if n < 3:
        curvature.fill(0.0)
        return curvature
    width = 0.5 * (x[2:] - x[:-2])
    curvature[1:-1] = 2.0 * (z[2:] - 2.0 * z[1:-1] + z[:-2]) / (width * width)
    curvature[0] = curvature[1]
    curvature[-1] = curvature[-2]
    return curvature


_RAIL_SLOPE_CACHE: "OrderedDict[tuple, np.ndarray]" = OrderedDict()
_RAIL_SLOPE_CACHE_SIZE = 512
# Off by default: measured on ``case_frog_N_strip05`` (101 samples, 8 contacts) the forces
# came back bitwise identical (max|dN| = 0.000e+00 N) but the wall clock did not move --
# 17.38 s fresh versus 17.67 s with the table, i.e. 0.98x.  Hashing a 2144-node profile
# costs about what the central difference it replaces costs, so the saving cancels.  It
# becomes profitable only once the key is the station index the caller already holds
# (no hash at all); until then the exact-but-inert path stays behind the switch.
#   VELCH_RAIL_SLOPE_TABLE=1   force it on (forces are unchanged)
RAIL_SLOPE_TABLE = os.environ.get("VELCH_RAIL_SLOPE_TABLE", "0") == "1"


def _rail_node_slopes(rail_y: np.ndarray, rail_z: np.ndarray,
                      surface_key) -> np.ndarray | None:
    """``dz/dy`` at the rail nodes, cached per station.

    The merged contact grid is dominated by rail nodes -- about 2000 of the 2144 points
    on a turnout station -- and the slope there is the same central difference no matter
    which axle or side is asking, so recomputing it once per contact call throws away the
    number of contacts per step.  Keyed on the station identity plus a fingerprint of the
    sampled profile, never on ``id``: ``ProfileSeries`` may hand out a fresh
    ``GraphProfile`` per sample, and a stale key here is what once turned a 170 kN peak
    into 1447 kN.

    Substituting the interpolated node slopes for a fresh difference on the merged grid
    is exact at rail nodes and is the same linear blend at the wheel nodes inserted
    between them, which is why the A/B run is asked for equality rather than closeness.
    """
    if not RAIL_SLOPE_TABLE or rail_y.size < 3:
        return None
    # Content fingerprint, not ``id`` and not the station label alone: ``ProfileSeries``
    # may hand out a fresh ``GraphProfile`` per sample, and two stations whose sampled
    # nodes hash the same are the same profile to within a floating-point bit -- which is
    # exactly the reuse this table is allowed to make.  The full-array hash costs about
    # a microsecond and buys immunity to the stale-key failure that once produced
    # 1447 kN; a three-point fingerprint is not enough to prove equality.
    key = (rail_y.size, hash(rail_z.tobytes()))
    cached = _RAIL_SLOPE_CACHE.get(key)
    if cached is not None:
        _RAIL_SLOPE_CACHE.move_to_end(key)
        return cached
    slopes = _grid_slope(rail_z, rail_y)
    _RAIL_SLOPE_CACHE[key] = slopes
    _RAIL_SLOPE_CACHE.move_to_end(key)
    while len(_RAIL_SLOPE_CACHE) > _RAIL_SLOPE_CACHE_SIZE:
        _RAIL_SLOPE_CACHE.popitem(last=False)
    return slopes


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
                 float(rail_z[-1]))
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
                 float(rail_z[-1]))
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
    stiffness_policy: str = "fixed_effective_radius",
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
    if not bool(np.all(wheel_y[1:] > wheel_y[:-1])):
        raise ValueError("wheel roll made the lower envelope non-monotonic in lateral y")
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
    slip_x = travel_speed_m_s + wheel_spin_rate_rad_s * g.lever_z_m
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
    linear_x = -law.creep_stiffness_x_n * slip_x / reference_speed
    linear_lateral = -law.creep_stiffness_lateral_n * slip_lateral / reference_speed
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
    if not bool(np.all(wheel_y[1:] > wheel_y[:-1])):
        raise ValueError("wheel roll made the lower envelope non-monotonic in lateral y")
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
