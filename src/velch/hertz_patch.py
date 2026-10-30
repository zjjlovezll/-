"""Hertz contact patch: the ellipse a normal contact actually occupies.

Why this module exists
----------------------
The solver's normal force has always been the point law ``F = C * delta**1.5``.  That is a
legitimate force law, but it says nothing about the *area* the force is carried on, and three
things need that area:

* **wear** -- Archard's law needs the sliding distance per unit area, and RCF indices need the
  pressure and the slip at the patch, not at a point;
* **tangential saturation** -- the creep coefficients ``f11``/``f22`` are properties of an ellipse
  (``f11 ~ a*b*C11``), so a constant pair of numbers is only valid for one patch size;
* **spin creep** -- ``M_z`` scales with ``a*b`` and vanishes when the patch degenerates.

This module therefore computes the ellipse from the two principal curvatures of the contacting
pair, using Hertz's theory with the Brewe-Hamrock (1977) coefficient form, which reduces exactly to
the classical circular solution when the curvature difference vanishes::

    alpha = (2 E(e) e / (pi (1 - e^2)))^(1/3)
    beta  = (2 E(e) e sqrt(1 - e^2) / pi)^(1/3)
    a     = alpha * (3 P / (2 * sum_rho * E_star))^(1/3)
    b     = beta  * (3 P / (2 * sum_rho * E_star))^(1/3)
    p0    = 3 P / (2 pi a b)

with ``e`` the ellipticity solved from the curvature difference

    F(rho) = ((2 - e^2) E(e) - 2 (1 - e^2) K(e)) / (e^2 E(e))

and ``F(rho) = (rho_y - rho_x) / (rho_y + rho_x)``, ``sum_rho = rho_x + rho_y``.

What this module deliberately does NOT do
-----------------------------------------
It does not change the normal force.  The frozen static anchor (59 680.5769 N at 65.47 um) is a
force law, and swapping the force law for an ellipse would move it.  The plan is to keep the force
law and use this patch for (i) reported area/pressure, (ii) the creep coefficients and spin term,
(iii) wear integration -- so that every existing number stays where it is until the calibration is
re-derived deliberately.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq
from scipy.special import ellipe, ellipk

__all__ = ["HertzPatch", "equivalent_modulus", "hertz_patch", "ellipticity_for"]


def equivalent_modulus(young_pa: float = 2.1e11, poisson: float = 0.3) -> float:
    """``E*`` for two steel bodies: ``E / (2 (1 - nu^2))``."""
    if not (young_pa > 0.0) or not (0.0 <= poisson < 0.5):
        raise ValueError("young_pa must be positive and poisson in [0, 0.5)")
    return young_pa / (2.0 * (1.0 - poisson * poisson))


def _curvature_difference_ratio(e: float) -> float:
    """``F(rho)`` as a function of the ellipticity ``e`` in (0, 1)."""
    if not (0.0 < e < 1.0):
        raise ValueError("ellipticity must lie strictly between 0 and 1")
    e2 = e * e
    ek = float(ellipk(e2))
    ee = float(ellipe(e2))
    return ((2.0 - e2) * ee - 2.0 * (1.0 - e2) * ek) / (e2 * ee)


def ellipticity_for(difference_ratio: float) -> float:
    """Solve ``F(rho) = ratio`` for the ellipticity.

    ``ratio = 0`` is the circular contact and returns ``e -> 0``; ``ratio -> 1`` is the line
    contact and returns ``e -> 1``.  The map is monotone on (0, 1), so a bracketed root find is
    both sufficient and stable.
    """
    f = float(difference_ratio)
    if not math.isfinite(f) or not (0.0 <= f <= 1.0):
        raise ValueError("the curvature difference ratio must lie in [0, 1]")
    if f <= 1.0e-12:
        return 1.0e-9
    if f >= 1.0 - 1.0e-12:
        return 1.0 - 1.0e-9
    return brentq(lambda e: _curvature_difference_ratio(e) - f, 1.0e-9, 1.0 - 1.0e-9, xtol=1e-12)


@dataclass(frozen=True)
class HertzPatch:
    """One contact ellipse, with the quantities wear and creep need."""

    normal_force_n: float
    semi_axis_a_m: float
    semi_axis_b_m: float
    peak_pressure_pa: float
    mean_pressure_pa: float
    area_m2: float
    ellipticity: float
    curvature_sum_1_per_m: float
    curvature_ratio: float
    equivalent_modulus_pa: float

    @property
    def area_mm2(self) -> float:
        return self.area_m2 * 1.0e6

    @property
    def semi_axis_a_mm(self) -> float:
        return self.semi_axis_a_m * 1.0e3

    @property
    def semi_axis_b_mm(self) -> float:
        return self.semi_axis_b_m * 1.0e3

    def as_dict(self) -> dict[str, float]:
        return {
            "normal_force_n": self.normal_force_n,
            "semi_axis_a_mm": self.semi_axis_a_mm,
            "semi_axis_b_mm": self.semi_axis_b_mm,
            "peak_pressure_pa": self.peak_pressure_pa,
            "mean_pressure_pa": self.mean_pressure_pa,
            "area_mm2": self.area_mm2,
            "ellipticity": self.ellipticity,
            "curvature_sum_1_per_m": self.curvature_sum_1_per_m,
            "curvature_ratio": self.curvature_ratio,
        }


def hertz_patch(
    normal_force_n: float,
    *,
    radius_x_m: float,
    radius_y_m: float,
    equivalent_modulus_pa: float | None = None,
) -> HertzPatch:
    """Hertz ellipse for two bodies with principal radii ``radius_x_m`` and ``radius_y_m``.

    ``radius_x_m`` is the rolling-direction radius (a wheel radius, since a rail is a much longer
    body in that direction) and ``radius_y_m`` the transverse one.  Both must be positive; a
    straight profile (infinite radius) is expressed by passing a large value rather than infinity,
    because the sum of curvatures is what enters the theory.
    """
    force = float(normal_force_n)
    if not math.isfinite(force) or force <= 0.0:
        raise ValueError("normal_force_n must be finite and positive")
    rx = float(radius_x_m)
    ry = float(radius_y_m)
    if not (math.isfinite(rx) and math.isfinite(ry)) or rx <= 0.0 or ry <= 0.0:
        raise ValueError("both principal radii must be finite and positive")

    modulus = float(equivalent_modulus_pa) if equivalent_modulus_pa is not None else equivalent_modulus()
    if not math.isfinite(modulus) or modulus <= 0.0:
        raise ValueError("equivalent_modulus_pa must be finite and positive")

    rho_x = 1.0 / rx
    rho_y = 1.0 / ry
    curvature_sum = rho_x + rho_y
    ratio = abs(rho_y - rho_x) / curvature_sum
    ellipticity = ellipticity_for(ratio)

    e2 = ellipticity * ellipticity
    ek = float(ellipk(e2))
    ee = float(ellipe(e2))
    # Brewe-Hamrock coefficients.  Both must tend to 1 as the ellipse becomes a circle
    # (eccentricity -> 0), which is what makes the circular sphere-on-plane solution come out
    # exactly; carrying an extra factor ``e`` here instead sends the circular contact to a point,
    # which the closed-form test caught at 0.01 mm.
    alpha = (2.0 * ee / (math.pi * (1.0 - e2))) ** (1.0 / 3.0)
    beta = (2.0 * ee * math.sqrt(1.0 - e2) / math.pi) ** (1.0 / 3.0)
    scale = (3.0 * force / (2.0 * curvature_sum * modulus)) ** (1.0 / 3.0)
    a = alpha * scale
    b = beta * scale
    area = math.pi * a * b
    peak = 3.0 * force / (2.0 * area)
    return HertzPatch(
        normal_force_n=force,
        semi_axis_a_m=max(a, b),
        semi_axis_b_m=min(a, b),
        peak_pressure_pa=peak,
        mean_pressure_pa=force / area,
        area_m2=area,
        ellipticity=ellipticity,
        curvature_sum_1_per_m=curvature_sum,
        curvature_ratio=ratio,
        equivalent_modulus_pa=modulus,
    )


def sphere_on_plane_patch(
    normal_force_n: float,
    *,
    radius_m: float,
    equivalent_modulus_pa: float | None = None,
) -> HertzPatch:
    """Circular limit, for validation: ``a = (3 F R / (4 E*))^(1/3)``."""
    return hertz_patch(
        normal_force_n,
        radius_x_m=radius_m,
        radius_y_m=radius_m,
        equivalent_modulus_pa=equivalent_modulus_pa,
    )


def _self_check() -> None:  # pragma: no cover - manual convenience
    import json

    patch = hertz_patch(59_680.5769, radius_x_m=0.43, radius_y_m=0.15)
    print(json.dumps(patch.as_dict(), indent=2))
    print("area_mm2", patch.area_mm2, "a_mm", patch.semi_axis_a_mm, "b_mm", patch.semi_axis_b_mm)


if __name__ == "__main__":  # pragma: no cover
    _self_check()
