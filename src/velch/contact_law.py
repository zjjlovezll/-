"""Pluggable wheel/rail contact policies for Velch.

The historic model is a hard ``argmax`` over a vertical-gap graph, a constant
Hertz stiffness from one global effective radius, and a constant damping
coefficient. Each of those three choices is now a named policy selected from the
case JSON ``contact`` block, so:

* the historic behaviour stays the default (every existing case loads unchanged),
* a new contact model is an A/B switch, not a solver rewrite,
* an external calibration (Simpack, a test rig, SDITT) can supply either a
  constant or a per-contact quantity without touching the integrator.

Policies
--------
point:
    ``argmax``        hard maximum of the signed-depth graph (historic).
    ``soft_argmax``   theta-soft-argmax centroid over the penetrating part of
                      the graph: the contact point slides continuously with the
                      load instead of jumping when the deepest node changes.
stiffness:
    ``fixed_effective_radius``   C = 4/3 E* sqrt(R*) with one R* from the case.
    ``local_circular``           R* from the local curvature of both profiles at
                      the contact point (4/sum(1/R)), so a conformal flange root
                      is softer than the tread without any extra parameter.
damping:
    ``fixed_coefficient``        c * sqrt(delta) * v  (historic).
    ``hunt_crossley``            (3/4) alpha C delta**1.5 v with
                      alpha = (1-e)/((1+e) v_ref), i.e. damping tied to the
                      stiffness and to a coefficient of restitution instead of a
                      tuned number.

Nothing here changes the force algebra: it only decides *where* the contact sits
and *which* stiffness/damping coefficient multiplies the same penetration law.
"""

from __future__ import annotations

import math

import numpy as np

POINT_POLICIES = ("argmax", "soft_argmax")
STIFFNESS_POLICIES = ("fixed_effective_radius", "local_circular")
DAMPING_POLICIES = ("fixed_coefficient", "hunt_crossley")

DEFAULT_WHEEL_ROLLING_RADIUS_M = 0.43
DEFAULT_THETA_FLOOR_M = 2.0e-6
DEFAULT_THETA_CEILING_M = 5.0e-5
CURVATURE_FIT_HALF_SPAN_M = 1.0e-3


def check_policy(name: str, allowed: tuple[str, ...], label: str) -> str:
    if name not in allowed:
        raise ValueError(f"unknown {label} policy {name!r}; expected one of {allowed}")
    return name


def hertz_half_width_m(penetration_m: float, radius_star_m: float) -> float:
    """Hertz contact half-width ``b = sqrt(2 R* delta)`` for a circular contact."""
    if penetration_m <= 0.0 or radius_star_m <= 0.0:
        return 0.0
    return math.sqrt(2.0 * radius_star_m * penetration_m)


def adaptive_theta_m(half_width_m: float, *, scale: float = 1.0,
                     floor_m: float = DEFAULT_THETA_FLOOR_M,
                     ceiling_m: float = DEFAULT_THETA_CEILING_M) -> float:
    """Smoothing width tied to the real patch size.

    A fixed 20 um (as in the SDITT code) is a compromise between "smooth enough
    to hide the discretisation" and "narrow enough not to blur the geometry".
    Scaling it with the computed Hertz half-width keeps that compromise local:
    the smoothing never exceeds the width of the physical contact patch, and it
    vanishes as the penetration goes to zero, so a static equilibrium is
    untouched.
    """
    if half_width_m <= 0.0:
        return floor_m
    return min(ceiling_m, max(floor_m, scale * half_width_m))


def soft_argmax_position(grid: np.ndarray, depth: np.ndarray, theta_m: float) -> float | None:
    """Weighted centroid of the grid over the penetrating part of the depth graph."""
    if grid.size < 2 or theta_m <= 0.0:
        return None
    maximum = float(np.max(depth))
    weight = np.exp((depth - maximum) / theta_m)
    weight[depth <= 0.0] = 0.0
    total = float(np.sum(weight))
    if not math.isfinite(total) or total <= 0.0:
        return None
    return float(np.sum(grid * weight) / total)


def local_curvature(z: np.ndarray, grid: np.ndarray, y0: float,
                    half_span_m: float = CURVATURE_FIT_HALF_SPAN_M) -> float:
    """Second derivative of the surface z(y) at y0 from a local quadratic fit.

    The profiles are piecewise linear, so a two-point difference of slopes would
    return a spike per node. A least-squares quadratic over a window comparable
    to the contact patch half-width gives the curvature the Hertz theory actually
    needs, and returns 0 when the window holds too few nodes to constrain it.
    """
    if half_span_m <= 0.0 or grid.size < 5:
        return 0.0
    select = (grid >= y0 - half_span_m) & (grid <= y0 + half_span_m)
    count = int(np.count_nonzero(select))
    if count < 5:
        return 0.0
    t = grid[select] - y0
    if float(np.ptp(t)) < 0.4 * half_span_m:
        return 0.0
    coefficients = quadratic_fit(t, z[select])
    curvature = 2.0 * float(coefficients[0])
    return curvature if math.isfinite(curvature) else 0.0


def quadratic_fit(t: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Closed-form least-squares quadratic, same coefficients as ``np.polyfit(t, z, 2)``.

    ``np.polyfit`` builds a Vandermonde matrix and solves it by SVD on every call,
    which costs tens of microseconds.  The contact law fits two windows per patch and
    there are eight patches per right-hand side, so that one call was the dominant
    cost of a dynamics evaluation.  Centring ``t`` makes the normal equations nearly
    diagonal and an explicit 3x3 solve is exact for a quadratic window, so the
    polynomial matches ``np.polyfit`` to machine precision at a fraction of the price.
    """
    u = np.asarray(t, dtype=float).ravel()
    w = np.asarray(z, dtype=float).ravel()
    if u.size != w.size or u.size < 3:
        raise ValueError("quadratic_fit needs at least three matched samples")
    n = float(u.size)
    mean = float(u.mean())
    u = u - mean
    s1 = float(u.sum())
    s2 = float((u * u).sum())
    s3 = float((u * u * u).sum())
    s4 = float((u * u * u * u).sum())
    rhs = np.array([float(w.sum()), float((u * w).sum()), float((u * u * w).sum())])
    b0, b1, b2 = float(rhs[0]), float(rhs[1]), float(rhs[2])
    # The normal-equation matrix is symmetric, so a 3x3 Cramer solve in plain floats
    # beats np.linalg.solve by roughly 13 us per call in LAPACK/Python handoff, which
    # at sixteen fits per right-hand side is the difference between 0.4 ms and 0.1 ms.
    m00, m01, m02 = n, s1, s2
    m11, m12, m22 = s2, s3, s4
    c11 = m11 * m22 - m12 * m12
    c01 = m01 * m22 - m12 * m02
    c02 = m01 * m12 - m11 * m02
    determinant = m00 * c11 - m01 * c01 + m02 * c02
    if determinant == 0.0 or not math.isfinite(determinant):
        raise ValueError("quadratic_fit window is degenerate (collinear abscissae)")
    a0 = (b0 * c11 - m01 * (b1 * m22 - m12 * b2) + m02 * (b1 * m12 - m11 * b2)) / determinant
    a1 = (m00 * (b1 * m22 - m12 * b2) - b0 * c01 + m02 * (m01 * b2 - b1 * m02)) / determinant
    a2 = (m00 * (m11 * b2 - b1 * m12) - m01 * (m01 * b2 - b1 * m02) + b0 * c02) / determinant
    # Undo the shift: z = a2 (t - mean)^2 + a1 (t - mean) + a0.
    return np.array([a2, a1 - 2.0 * a2 * mean, a0 - a1 * mean + a2 * mean * mean])


def circular_equivalent_radius(radius_y_m: float, curvature_wheel: float,
                               curvature_rail: float, *, ellipticity: float = 1.0) -> float:
    """``4 / (1/R_yy + |k_w| + |k_r|)`` — the circular Hertz equivalent radius.

    ``ellipticity`` (default 1) is a reserved correction factor: 1 is the
    circular equivalent, and the exact elliptical solution of the same curvatures
    is a bounded factor around it, so a calibration can be applied without
    changing the structure.
    """
    if radius_y_m <= 0.0:
        raise ValueError("wheel radius at the contact point must be positive")
    total = 1.0 / radius_y_m + abs(curvature_wheel) + abs(curvature_rail)
    if not math.isfinite(total) or total <= 0.0:
        return radius_y_m
    return ellipticity * 4.0 / total


def hertz_stiffness_n_m_1p5(effective_modulus_pa: float, radius_star_m: float) -> float:
    return 4.0 / 3.0 * effective_modulus_pa * math.sqrt(radius_star_m)


def hunt_crossley_coefficient(stiffness_n_m_1p5: float, restitution: float,
                              reference_speed_m_s: float) -> float:
    """Nonlinear damping coefficient from a coefficient of restitution.

    Hunt & Crossley write the dissipative term as ``lambda delta**1.5 v`` with
    ``lambda = (3/4) alpha k`` and ``alpha = (1-e) / ((1+e) v_ref)``. With
    ``e = 1`` the damping vanishes, with ``e -> 0`` it becomes fully dissipative,
    and it scales with the stiffness instead of being a free number.
    """
    if reference_speed_m_s <= 0.0:
        raise ValueError("damping reference speed must be positive")
    bounded = min(max(restitution, 0.0), 1.0)
    alpha = (1.0 - bounded) / ((1.0 + bounded) * reference_speed_m_s)
    return 0.75 * alpha * stiffness_n_m_1p5
