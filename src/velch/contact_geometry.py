"""C2 spline contact geometry (roadmap stage S1).

The grid path in :mod:`velch.contact` samples both surfaces on a merged grid and
takes the ``argmax`` of a signed depth. Two errors follow from that: the contact
position is limited to a grid node (0.05 mm today, which is 1-2 % of the patch
half-width), and the curvature that feeds ``R*`` comes from a quadratic fit over
a sampled array, so it inherits the sampling noise.

This module replaces both steps. Each surface band is fitted with a C2 cubic
spline, the clearance ``g(y) = z_rail(y) - z_wheel(y)`` is then an analytic
function, and every local extremum of ``g`` is found by bracketing the roots of
``g'(y)`` and refining them with Brent. The deepest one is the contact point, and
``g''`` there gives the exact curvatures.

Nothing here reads or writes the case schema yet: :func:`swept_contact` returns a
:class:`SweptContact` whose fields mirror :class:`velch.contact.ContactGeometry`
plus the two curvatures, so a caller can compare the two paths field by field.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq

__all__ = [
    "SplineProfile",
    "SweptContact",
    "absolute_surfaces",
    "curvature_at",
    "fit_profile",
    "swept_contact",
]

DEFAULT_SCAN_STEP_M = 2.5e-4
"""Spacing of the coarse scan that brackets the roots of ``g'``.

The scan does not set the answer: every bracket is refined to machine precision
with Brent, so the spacing only has to be fine enough that no branch of ``g`` is
missed. At 0.25 mm a 20 mm wide flange groove still holds 80 samples.
"""

DEFAULT_CURVATURE_HALF_SPAN_M = 1.0e-3
"""Half-width of the window the curvature is measured over.

An interpolating spline passes through every digitised point, so its second
derivative carries the drawing noise at the node spacing (0.1-0.5 mm), which for
a 1:40 taper reports ``R* ~ 0.1 m`` instead of ``0.55 m``. Curvature therefore
has to be measured at the scale of the contact patch, not at the node scale: the
same least-squares quadratic that :func:`velch.contact_law.local_curvature`
applies to the merged grid is applied here to the spline, so it no longer
depends on the grid at all. 1 mm matches the default used by that grid path.
"""


@dataclass(frozen=True)
class SplineProfile:
    """A surface band ``z(y)`` held as a C2 cubic spline."""

    y_m: np.ndarray
    z_m: np.ndarray
    spline: CubicSpline
    y_lo_m: float
    y_hi_m: float
    max_residual_m: float
    name: str

    def z(self, y: float) -> float:
        return float(self.spline(y))

    def dz(self, y: float) -> float:
        return float(self.spline(y, 1))

    def d2z(self, y: float) -> float:
        return float(self.spline(y, 2))

    def covers(self, y: float) -> bool:
        return self.y_lo_m <= y <= self.y_hi_m


def fit_profile(y_m, z_m, *, y_lo_m: float | None = None, y_hi_m: float | None = None,
                max_residual_m: float = 2.0e-6, name: str = "") -> SplineProfile:
    """Fit ``z(y)`` over ``[y_lo_m, y_hi_m]`` and verify the residual.

    Points are sorted and duplicate abscissae are averaged (the profile files
    contain repeated y at tangent discontinuities). The fit raises when the
    residual exceeds ``max_residual_m`` instead of silently returning a surface
    that does not represent the file.
    """
    y = np.asarray(y_m, dtype=float)
    z = np.asarray(z_m, dtype=float)
    if y.shape != z.shape or y.ndim != 1:
        raise ValueError("profile arrays must be one dimensional and the same length")
    order = np.argsort(y, kind="stable")
    y, z = y[order], z[order]
    lo = float(y[0] if y_lo_m is None else y_lo_m)
    hi = float(y[-1] if y_hi_m is None else y_hi_m)
    if not hi > lo:
        raise ValueError("profile band must be increasing")
    keep = (y >= lo) & (y <= hi)
    y, z = y[keep], z[keep]
    if y.size < 6:
        raise ValueError(f"need at least six points inside the band, got {y.size}")
    # Average repeated abscissae so CubicSpline sees a strictly increasing axis.
    unique, inverse = np.unique(y, return_inverse=True)
    if unique.size != y.size:
        totals = np.zeros(unique.size)
        counts = np.zeros(unique.size)
        np.add.at(totals, inverse, z)
        np.add.at(counts, inverse, 1.0)
        z = totals / counts
        y = unique
        if y.size < 6:
            raise ValueError("band collapses to fewer than six distinct abscissae")
    spline = CubicSpline(y, z, bc_type="natural", extrapolate=False)
    # An interpolating spline passes through every node, so a residual measured at
    # the nodes is identically zero and proves nothing. What can go wrong is the
    # *overshoot between* nodes: a step or a re-entrant corner makes the cubic
    # swing beyond the digitised polyline. The gate below compares the spline at
    # the node midpoints with the polyline there, which bounds that swing.
    midpoints = 0.5 * (y[1:] + y[:-1])
    polyline = 0.5 * (z[1:] + z[:-1])
    residual = float(np.max(np.abs(np.asarray(spline(midpoints)) - polyline)))
    if not math.isfinite(residual) or residual > max_residual_m:
        raise ValueError(
            f"profile band {name or '<unnamed>'} does not fit a cubic spline: "
            f"overshoot between nodes {residual * 1e6:.3f} um > "
            f"{max_residual_m * 1e6:.3f} um"
        )
    return SplineProfile(y_m=y, z_m=z, spline=spline, y_lo_m=float(y[0]),
                         y_hi_m=float(y[-1]), max_residual_m=residual, name=name)


@dataclass(frozen=True)
class SegmentedProfile:
    """A surface band held as a chain of spline pieces.

    ``swept_contact`` only consumes ``z``, ``dz``, ``d2z``, ``y_lo_m`` and
    ``y_hi_m``, so a segmented band is a drop-in replacement. That matters: the
    cure for a profile a single cubic cannot represent (a flange root, a re-entrant
    corner) is to split the *representation*, not the *search*. Running a separate
    contact solve on every piece would let a spurious pair -- the flange tip against
    the floor of a filled flangeway -- beat the true tread contact, which is exactly
    the failure the merged-grid path avoids by construction.
    """

    pieces: tuple[SplineProfile, ...]
    starts: tuple[float, ...]
    y_lo_m: float
    y_hi_m: float
    max_residual_m: float
    name: str
    relaxed_residual_m: tuple[float, ...] = ()

    def covers(self, y: float) -> bool:
        return self.y_lo_m <= y <= self.y_hi_m

    def piece_at(self, y: float) -> SplineProfile:
        if not self.pieces:
            raise ValueError("segmented profile has no pieces")
        index = int(np.searchsorted(np.asarray(self.starts), y, side="right")) - 1
        index = min(max(index, 0), len(self.pieces) - 1)
        return self.pieces[index]

    def z(self, y: float) -> float:
        return self.piece_at(y).z(y)

    def dz(self, y: float) -> float:
        return self.piece_at(y).dz(y)

    def d2z(self, y: float) -> float:
        return self.piece_at(y).d2z(y)

    def spline(self, y, nu: int = 0):
        """Evaluate like ``CubicSpline.__call__`` so helpers that hold a spline work.

        ``curvature_at`` fits a quadratic through ``surface.spline(ys)``; accepting
        an array here keeps that helper unchanged for both representations.
        """
        values = np.atleast_1d(np.asarray(y, dtype=float))
        out = np.empty(values.size, dtype=float)
        for index, value in enumerate(values):
            out[index] = self.piece_at(float(value)).spline(float(value), nu)
        if np.ndim(y) == 0:
            return float(out[0])
        return out


def fit_segmented(y_m, z_m, *, max_residual_m: float = 2.0e-6,
                  min_nodes: int = 6, max_depth: int = 12,
                  name: str = "") -> SegmentedProfile:
    """Fit ``z(y)`` as the fewest spline pieces that each pass the overshoot gate.

    A single cubic cannot represent a wheel profile (the flange root turns far too
    quickly: the gate rejects it with a ~397 um overshoot) nor a turnout section with
    a relief cut. Bisecting a failing band converges on the largest representable
    sub-bands, which is the segmentation a polyarc description would give in closed
    form -- only here it is derived from the gate instead of hand-calibrated.

    Failures that survive to the minimum node count are kept as a single piece with
    its overshoot recorded in ``relaxed_residual_m``. Coverage is therefore total: a
    hole in the band would silently change the contact search, which is worse than a
    bounded local wobble of a few um.
    """
    y = np.asarray(y_m, dtype=float)
    z = np.asarray(z_m, dtype=float)
    if y.shape != z.shape or y.ndim != 1:
        raise ValueError("profile arrays must be one dimensional and the same length")
    order = np.argsort(y, kind="stable")
    y, z = y[order], z[order]
    if y.size < min_nodes:
        raise ValueError(f"need at least {min_nodes} points, got {y.size}")

    # ``fit_profile`` needs six points, so the segment floor cannot go below that;
    # resolution has to come from ``max_depth`` instead.
    min_nodes = max(int(min_nodes), 6)

    pieces: list[SplineProfile] = []
    relaxed: list[float] = []

    def split(lo: int, hi: int, depth: int) -> None:
        try:
            pieces.append(fit_profile(y[lo:hi + 1], z[lo:hi + 1],
                                      max_residual_m=max_residual_m, name=name))
            return
        except ValueError:
            if depth < max_depth and hi - lo + 1 >= 2 * min_nodes:
                mid = (lo + hi) // 2
                split(lo, mid, depth + 1)
                split(mid, hi, depth + 1)
                return
        # The band still straddles the discontinuity at the finest split allowed.
        # Keeping the surface *whole* matters more than the gate here: a hole in the
        # band would silently change the contact search, while the overshoot is a
        # bounded local wobble that is reported through ``max_residual_m``.
        piece = fit_profile(y[lo:hi + 1], z[lo:hi + 1],
                            max_residual_m=math.inf, name=name)
        relaxed.append(piece.max_residual_m)
        pieces.append(piece)

    split(0, y.size - 1, 0)
    if not pieces:
        raise ValueError(f"profile band {name or '<unnamed>'} could not be segmented")
    pieces.sort(key=lambda piece: piece.y_lo_m)
    return SegmentedProfile(
        pieces=tuple(pieces),
        starts=tuple(piece.y_lo_m for piece in pieces),
        y_lo_m=float(pieces[0].y_lo_m),
        y_hi_m=float(pieces[-1].y_hi_m),
        max_residual_m=max((piece.max_residual_m for piece in pieces), default=0.0),
        name=name,
        relaxed_residual_m=tuple(relaxed),
    )


def absolute_surfaces(wheel_profile, rail_sample, *, wheel_y_m: float, wheel_z_m: float,
                      wheel_roll_rad: float, wheel_lateral_offset_m: float,
                      rail_y_m: float, rail_z_m: float
                      ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Place both profile bands in the track frame, exactly as the grid path does.

    Kept next to :func:`swept_contact` so a caller can feed both paths from one
    transform instead of duplicating the roll and offset algebra.
    """
    local_y = wheel_lateral_offset_m + wheel_profile.y_m
    local_z = wheel_profile.z_m
    c, s = math.cos(wheel_roll_rad), math.sin(wheel_roll_rad)
    wheel_y = wheel_y_m + c * local_y - s * local_z
    wheel_z = wheel_z_m + s * local_y + c * local_z
    rail_y = rail_y_m + rail_sample.profile.y_m
    rail_z = rail_z_m + rail_sample.profile.z_m
    return wheel_y, wheel_z, rail_y, rail_z


def curvature_at(surface: SplineProfile, y0: float,
                 half_span_m: float = DEFAULT_CURVATURE_HALF_SPAN_M,
                 samples: int = 21) -> float:
    """Second derivative of ``z(y)`` at ``y0`` measured over ``±half_span_m``.

    A least-squares quadratic over the window, evaluated on the spline instead of
    on a merged grid. Returns 0 when the window leaves the fitted band.
    """
    lo, hi = y0 - half_span_m, y0 + half_span_m
    if lo < surface.y_lo_m or hi > surface.y_hi_m:
        lo = max(lo, surface.y_lo_m)
        hi = min(hi, surface.y_hi_m)
        if hi - lo < 0.4 * 2.0 * half_span_m:
            return 0.0
    ys = np.linspace(lo, hi, samples)
    t = ys - y0
    coefficients = np.polyfit(t, surface.spline(ys), 2)
    curvature = 2.0 * float(coefficients[0])
    return curvature if math.isfinite(curvature) else 0.0


@dataclass(frozen=True)
class SweptContact:
    """Contact state from the analytic path; mirrors ``ContactGeometry``."""

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
    slope: float
    curvature_wheel_1_m: float
    curvature_rail_1_m: float
    radius_y_m: float
    radius_star_m: float
    stiffness_n_m_1p5: float | None
    half_width_m: float
    edge_limited: bool
    extrema_count: int


def swept_contact(wheel: SplineProfile, rail: SplineProfile, *,
                  wheel_origin_y_m: float, wheel_origin_z_m: float,
                  effective_modulus_pa: float | None = None,
                  ellipticity: float = 1.0,
                  scan_step_m: float = DEFAULT_SCAN_STEP_M,
                  curvature_half_span_m: float = DEFAULT_CURVATURE_HALF_SPAN_M,
                  lower: float | None = None,
                  upper: float | None = None) -> SweptContact | None:
    """Deepest interference between two spline surfaces over their overlap.

    ``wheel_origin_y_m`` / ``wheel_origin_z_m`` are the wheel reference plane and
    wheel centre height in the same absolute frame as the profiles; they are only
    used for the moment arms and the local wheel radius.
    """
    lo = max(wheel.y_lo_m, rail.y_lo_m, -math.inf if lower is None else lower)
    hi = min(wheel.y_hi_m, rail.y_hi_m, math.inf if upper is None else upper)
    if not hi > lo:
        return None

    def clearance(y: float) -> float:
        return rail.z(y) - wheel.z(y)

    def derivative(y: float) -> float:
        return rail.dz(y) - wheel.dz(y)

    count = int(math.ceil((hi - lo) / scan_step_m))
    samples = np.linspace(lo, hi, max(count + 1, 3))
    values = np.array([derivative(float(y)) for y in samples])
    candidates = [lo, hi]
    for index in range(samples.size - 1):
        left, right = float(values[index]), float(values[index + 1])
        if left == 0.0:
            candidates.append(float(samples[index]))
            continue
        if left * right < 0.0:
            try:
                root = brentq(derivative, float(samples[index]),
                              float(samples[index + 1]), xtol=1e-14, rtol=1e-15)
            except (ValueError, RuntimeError):
                continue
            candidates.append(float(root))
    if values[-1] == 0.0:
        candidates.append(hi)

    best: tuple[float, float, bool] | None = None
    for y in candidates:
        slope = rail.dz(y)
        inv = 1.0 / math.sqrt(1.0 + slope * slope)
        depth = clearance(y) * inv
        edge = y <= lo + 1e-12 or y >= hi - 1e-12
        if best is None or depth > best[0]:
            best = (depth, y, edge)
    if best is None:
        return None
    depth, y, edge = best
    slope = rail.dz(y)
    inv = 1.0 / math.sqrt(1.0 + slope * slope)
    wheel_z = wheel.z(y)
    rail_z = rail.z(y)
    curvature_wheel = curvature_at(wheel, y, curvature_half_span_m)
    curvature_rail = curvature_at(rail, y, curvature_half_span_m)
    radius_y = max(1.0e-6, wheel_origin_z_m - wheel_z)
    radius_star = 0.0
    stiffness = None
    if effective_modulus_pa is not None:
        total = 1.0 / radius_y + abs(curvature_wheel) + abs(curvature_rail)
        radius_star = ellipticity * 4.0 / total if total > 0.0 else radius_y
        stiffness = 4.0 / 3.0 * effective_modulus_pa * math.sqrt(radius_star)
    penetration = max(0.0, depth)
    half_width = (math.sqrt(2.0 * radius_star * penetration)
                  if penetration > 0.0 and radius_star > 0.0 else 0.0)
    return SweptContact(
        y_m=y,
        wheel_z_m=wheel_z,
        rail_z_m=rail_z,
        penetration_m=penetration,
        normal_y=-slope * inv,
        normal_z=inv,
        tangent_y=inv,
        tangent_z=slope * inv,
        lever_y_m=y - wheel_origin_y_m,
        lever_z_m=wheel_z - wheel_origin_z_m,
        slope=slope,
        curvature_wheel_1_m=curvature_wheel,
        curvature_rail_1_m=curvature_rail,
        radius_y_m=radius_y,
        radius_star_m=radius_star,
        stiffness_n_m_1p5=stiffness,
        half_width_m=half_width,
        edge_limited=edge,
        extrema_count=len(candidates),
    )
