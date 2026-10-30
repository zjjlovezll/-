"""Parameter dataclasses and the contact response records.

Split out of :mod:`velch.contact` so the data contract can be imported (by the case loader,
the model settings, the tests) without dragging in the geometry searches or the force law.
The policy tuples live here because they belong to the parameters they constrain.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .contact_law import (DAMPING_POLICIES, POINT_POLICIES, STIFFNESS_POLICIES,
                          check_policy)
from .support_compliance import series_normal_force


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
    #: When true the creep coefficients are recomputed from the measured contact ellipse
    #: (``f11 = 2 E* a b C11``) instead of being taken from the constants above.  Off by default so
    #: every archived run keeps the coefficients it was measured with.
    creep_stiffness_from_patch: bool = False
    #: Kalker's circular shape factors (nu = 0.3).  Ellipticity dependence is not implemented.
    creep_shape_x: float = 0.98
    creep_shape_lateral: float = 0.99
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
