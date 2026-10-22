"""Independent references for wheel-rail contact geometry.

The point of this module is to be *not another discretisation of the same profiles*.
Every entry here has a closed form that can be evaluated without looking at a grid, a
spline, or any node spacing, so agreement between ``find_graph_contact`` and a reference
carries information that agreement between two grids cannot.

Evidence levels are declared per reference and must be repeated in any report:

``analytic``
    Closed form, exact for the geometry it describes (circle-circle line contact,
    Hertz point contact). Level A.
``finer_grid``
    The same profiles sampled much more finely. It is a discretisation, so it only
    bounds the grid's own quantisation error -- never the model's. Level B.
``literature``
    A number taken from a publication. Level C, and only usable when the geometry is
    stated precisely enough to be the same problem.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

EVIDENCE_LEVELS = ("analytic", "finer_grid", "literature")


@dataclass(frozen=True)
class ReferenceContact:
    """One reference answer for a wheel/rail pair."""

    method: str
    evidence: str
    y_m: float
    penetration_m: float
    radius_star_m: float | None
    normal_force_n: float | None
    note: str = ""


def hertz_point_force(radius_star_m: float, penetration_m: float,
                      effective_modulus_pa: float) -> float:
    """``N = (4/3) E* sqrt(R*) delta^(3/2)`` -- the closed form the laws must match."""

    if radius_star_m <= 0.0:
        raise ValueError("radius_star_m must be positive")
    if penetration_m <= 0.0:
        return 0.0
    return (4.0 / 3.0) * effective_modulus_pa * math.sqrt(radius_star_m) * penetration_m ** 1.5


def hertz_point_stiffness(radius_star_m: float, effective_modulus_pa: float) -> float:
    """``C`` in ``N = C delta^(3/2)``, for comparing against a fitted stiffness."""

    if radius_star_m <= 0.0:
        raise ValueError("radius_star_m must be positive")
    return (4.0 / 3.0) * effective_modulus_pa * math.sqrt(radius_star_m)


def circle_through(y: np.ndarray, z: np.ndarray) -> tuple[float, float, float]:
    """Circle through three points, returned as ``(centre_y, centre_z, radius)``.

    Used to read a curvature off profile nodes *without* differentiating twice, so a
    curvature check does not inherit the same stencil error as the solver.
    """

    y = np.asarray(y, dtype=float)
    z = np.asarray(z, dtype=float)
    if y.size != 3 or z.size != 3:
        raise ValueError("circle_through needs exactly three points")
    (y0, y1, y2), (z0, z1, z2) = y, z
    denominator = 2.0 * (y0 * (z1 - z2) + y1 * (z2 - z0) + y2 * (z0 - z1))
    if abs(denominator) < 1.0e-18:
        raise ValueError("three points are colinear; curvature is infinite")
    s0 = y0 * y0 + z0 * z0
    s1 = y1 * y1 + z1 * z1
    s2 = y2 * y2 + z2 * z2
    centre_y = (s0 * (z1 - z2) + s1 * (z2 - z0) + s2 * (z0 - z1)) / denominator
    centre_z = (s0 * (y2 - y1) + s1 * (y0 - y2) + s2 * (y1 - y0)) / denominator
    radius = math.hypot(y0 - centre_y, z0 - centre_z)
    return centre_y, centre_z, radius


def circle_line_contact(wheel_centre_y_m: float, wheel_centre_z_m: float,
                        wheel_radius_m: float, rail_centre_y_m: float,
                        rail_centre_z_m: float, rail_radius_m: float
                        ) -> ReferenceContact:
    """Exact contact of two circular profiles (a wheel tread on a rail crown head).

    Both circles are convex (rail crown below the wheel, so the rail centre sits *below*
    its surface). The contact point lies on the line joining the centres, and the
    penetration is the overlap of the two radii minus the centre distance.
    """

    for name, value in (("wheel_radius_m", wheel_radius_m), ("rail_radius_m", rail_radius_m)):
        if value <= 0.0:
            raise ValueError(f"{name} must be positive")
    dy = rail_centre_y_m - wheel_centre_y_m
    dz = rail_centre_z_m - wheel_centre_z_m
    distance = math.hypot(dy, dz)
    if distance <= 0.0:
        raise ValueError("the two centres coincide")
    sum_radius = wheel_radius_m + rail_radius_m
    penetration = sum_radius - distance
    # Contact point: from the wheel centre toward the rail centre, at the wheel radius.
    y_contact = wheel_centre_y_m + dy / distance * wheel_radius_m
    radius_star = (wheel_radius_m * rail_radius_m) / sum_radius
    return ReferenceContact(
        method="circle_line_contact",
        evidence="analytic",
        y_m=y_contact,
        penetration_m=max(0.0, penetration),
        radius_star_m=radius_star,
        normal_force_n=None,
        note="" if penetration > 0.0 else "no contact: circles are separated",
    )


def hertz_from_reference(reference: ReferenceContact, effective_modulus_pa: float,
                         method: str = "hertz_point") -> ReferenceContact:
    """Attach the closed-form normal force to a geometric reference."""

    if reference.radius_star_m is None:
        raise ValueError("reference carries no radius_star_m")
    force = hertz_point_force(reference.radius_star_m, reference.penetration_m,
                             effective_modulus_pa)
    return ReferenceContact(
        method=f"{reference.method}+{method}",
        evidence=reference.evidence,
        y_m=reference.y_m,
        penetration_m=reference.penetration_m,
        radius_star_m=reference.radius_star_m,
        normal_force_n=force,
        note=reference.note,
    )


def finer_grid_reference(wheel_y: np.ndarray, wheel_z: np.ndarray,
                         rail_y: np.ndarray, rail_z: np.ndarray,
                         samples: int = 400001) -> ReferenceContact:
    """Sample the same surfaces far more finely than the solver does.

    This is a bounded cross-check, not truth: it can only reveal how much the solver's
    own sampling moved the answer. It is declared ``finer_grid`` (level B) so a report
    cannot accidentally present it as an independent solution.
    """

    if samples < 1001:
        raise ValueError("samples must be at least 1001 to be finer than the solver")
    lower = max(float(wheel_y.min()), float(rail_y.min()))
    upper = min(float(wheel_y.max()), float(rail_y.max()))
    if not upper > lower:
        raise ValueError("profiles do not overlap")
    grid = np.linspace(lower, upper, samples)
    gap = np.interp(grid, rail_y, rail_z) - np.interp(grid, wheel_y, wheel_z)
    index = int(np.argmax(gap))
    depth = float(gap[index])
    if depth <= 0.0:
        return ReferenceContact("finer_grid", "finer_grid", float(grid[index]), 0.0,
                                None, 0.0, note="no contact at this placement")
    span = 3
    lo = max(0, index - span)
    hi = min(grid.size, index + span + 1)
    curvature = _gap_curvature(grid[lo:hi], gap[lo:hi])
    radius_star = None if curvature is None or curvature <= 0.0 else 1.0 / curvature
    return ReferenceContact("finer_grid", "finer_grid", float(grid[index]), depth,
                            radius_star, None,
                            note=f"{samples} samples over {upper - lower:.6f} m")


def _gap_curvature(y: np.ndarray, gap: np.ndarray) -> float | None:
    """Signed curvature of the gap at its minimum, from a quadratic through 3 nodes."""

    if y.size < 3:
        return None
    order = np.argsort(y)
    y = y[order]
    gap = gap[order]
    index = int(np.argmax(gap))
    if index == 0 or index == y.size - 1:
        return None
    y0, y1, y2 = y[index - 1], y[index], y[index + 1]
    g0, g1, g2 = gap[index - 1], gap[index], gap[index + 1]
    span = y2 - y0
    if span <= 0.0:
        return None
    # Second difference on a non-uniform triple, divided by the local scale.
    second = 2.0 * (g0 * (y1 - y2) + g1 * (y2 - y0) + g2 * (y0 - y1)) / span
    return float(second / max(1.0e-12, (y1 - y0) * (y2 - y1)))
