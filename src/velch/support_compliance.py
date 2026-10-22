"""Rail support compliance under a moving wheel (S1-e).

The rail is not carried by a continuous spring: it sits on discrete fasteners
every ``spacing_m`` (0.6 m for the CN18 turnout sleepers). A wheel rolling along
such a rail sees a support stiffness that rises when it is over a sleeper and
falls between two of them, so the contact force carries a component at the
sleeper passing frequency ``v / spacing`` (97.2 / 0.6 = 162 Hz at 350 km/h).

The model here is the classical static series compliance: the wheel approaches
the *undeformed* rail top by ``delta``, part of it is taken by the Hertzian
contact spring and part by the rail settling on its fasteners,

    delta = (N / C) ** (2/3) + N * G(x),      G(x) = rail deflection per unit load

with ``G`` the Green function of an Euler-Bernoulli beam on discrete spring
supports, evaluated for the load at the wheel. ``G`` is periodic in
``x / spacing`` and is precomputed once on a small FE model; only its table is
used at run time, so the hot path costs one interpolation.

SDITT reference values (`Par_TrackSystem.m`, FT-Modal / FT-FEM path):
RailPad Stiff_X/Y/Z = 20e6 / 20e6 / 25e6 N/m, Damp = 20e3 N s/m,
Er = 214e9 Pa; 60 kg rail EI = 6.55e6 N m^2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


def beam_element_matrix(ei: float, length: float) -> np.ndarray:
    """Euler-Bernoulli beam element (w, theta) x (w, theta)."""
    le = length
    return ei / le ** 3 * np.array(
        [[12.0, 6.0 * le, -12.0, 6.0 * le],
         [6.0 * le, 4.0 * le * le, -6.0 * le, 2.0 * le * le],
         [-12.0, -6.0 * le, 12.0, -6.0 * le],
         [6.0 * le, 2.0 * le * le, -6.0 * le, 4.0 * le * le]],
        dtype=float,
    )


def beam_point_load(length: float, a: float) -> np.ndarray:
    """Consistent nodal load of a unit point load at ``a`` inside an element."""
    le = length
    b = le - a
    return np.array([b * b * (3.0 * a + b) / le ** 3,
                     a * b * b * (a - b) / le ** 2,
                     a * a * (a + 3.0 * b) / le ** 3,
                     -a * a * b * (a - b) / le ** 2], dtype=float)


def _green_function(spacing_m: float, pad_stiffness_n_m: float, rail_ei_n_m2: float,
                    samples: int, elements_per_pitch: int) -> np.ndarray:
    """Static deflection under the load over one pitch, in m/N."""
    pitch_nodes = elements_per_pitch
    element = spacing_m / pitch_nodes
    # Five pitches: the load sits in the third one, so the clamped window
    # ends are two whole pitches (1.2 m) away, outside the influence length
    # 1/beta of a 60 kg rail on 25 MN/m pads (about 0.9 m).
    spans = 5
    node_count = spans * pitch_nodes + 1
    dof = 2 * node_count
    stiffness = np.zeros((dof, dof))
    element_matrix = beam_element_matrix(rail_ei_n_m2, element)
    for e in range(node_count - 1):
        idx = np.arange(2 * e, 2 * e + 4)
        stiffness[np.ix_(idx, idx)] += element_matrix
    for node in range(0, node_count + 1, pitch_nodes):
        if node >= node_count:
            continue
        stiffness[2 * node, 2 * node] += pad_stiffness_n_m
    # Clamp the two extremes of the sliding window: the third support is interior.
    for node in (0, node_count - 1):
        stiffness[2 * node, :] = 0.0
        stiffness[2 * node + 1, :] = 0.0
        stiffness[2 * node, 2 * node] = 1.0
        stiffness[2 * node + 1, 2 * node + 1] = 1.0
    table = np.empty(samples)
    for i, u in enumerate(np.linspace(0.0, spacing_m, samples)):
        position = 2.0 * spacing_m + u  # third pitch: real supports on both sides
        e = min(int(position // element), node_count - 2)
        local = position - e * element
        load = np.zeros(dof)
        load[2 * e:2 * e + 4] += beam_point_load(element, local)
        # Solve with the load, then read the deflection where it is applied:
        # interpolate between the two nodes with the same cubic weights.
        displacement = np.linalg.solve(stiffness, load)
        weights = beam_point_load(element, local)
        table[i] = (weights[0] * displacement[2 * e] + weights[1] * 0.0
                    + weights[2] * displacement[2 * e + 2] + weights[3] * 0.0)
    return table


@dataclass(frozen=True)
class SupportCompliance:
    """Periodic rail-settling compliance of a discretely supported rail."""

    spacing_m: float
    pad_stiffness_n_m: float
    rail_ei_n_m2: float
    samples: int = 41
    elements_per_pitch: int = 8
    table_m_per_n: np.ndarray = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        for name in ("spacing_m", "pad_stiffness_n_m", "rail_ei_n_m2"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"support compliance {name} must be positive and finite")
        if self.samples < 5:
            raise ValueError("support compliance samples must be at least 5")
        if self.elements_per_pitch < 2:
            raise ValueError("support compliance elements_per_pitch must be at least 2")
        table = _green_function(self.spacing_m, self.pad_stiffness_n_m,
                                self.rail_ei_n_m2, self.samples, self.elements_per_pitch)
        object.__setattr__(self, "table_m_per_n", table)

    def at(self, station_m: float) -> float:
        """Settling compliance in m/N at a station along the rail."""
        if not math.isfinite(station_m):
            raise ValueError("station must be finite")
        u = (station_m % self.spacing_m) / self.spacing_m
        grid = np.linspace(0.0, 1.0, self.table_m_per_n.size)
        return float(np.interp(u, grid, self.table_m_per_n))

    @property
    def mean_m_per_n(self) -> float:
        return float(np.mean(self.table_m_per_n))


def series_normal_force(depth_m: float, stiffness_n_m_1p5: float,
                        support_compliance_m_per_n: float | None) -> float:
    """Elastic normal force of the contact spring in series with the support.

    Solves ``delta = (N/C)^(2/3) + N * G`` for ``N`` with Newton; the left side
    is monotone in ``N`` so five iterations are ample for engineering accuracy.
    """
    if not (depth_m > 0.0) or not math.isfinite(depth_m):
        return 0.0
    if not support_compliance_m_per_n or support_compliance_m_per_n <= 0.0:
        return stiffness_n_m_1p5 * depth_m ** 1.5
    if stiffness_n_m_1p5 <= 0.0:
        raise ValueError("contact stiffness must be positive")
    two_thirds = stiffness_n_m_1p5 ** (-2.0 / 3.0)
    force = stiffness_n_m_1p5 * depth_m ** 1.5
    for _ in range(5):
        residual = two_thirds * force ** (2.0 / 3.0) + support_compliance_m_per_n * force - depth_m
        slope = (2.0 / 3.0) * two_thirds * force ** (-1.0 / 3.0) + support_compliance_m_per_n
        step = residual / slope
        force = max(force - step, 1e-9)
    return float(force)


def series_normal_force_slope(depth_m: float, stiffness_n_m_1p5: float,
                              support_compliance_m_per_n: float | None) -> float:
    """``dN/ddelta`` of :func:`series_normal_force`, by implicit differentiation.

    Differentiating ``delta = (N/C)^(2/3) + N*G`` gives

        dN/ddelta = 1 / ( (2/3) * (N/C)^(-1/3) / C + G )

    which is exact for the solved ``N`` and free of the iteration-count staircase
    that a finite difference of the five-Newton solve would inherit. With no
    support compliance the law is pure Hertz and the closed form is
    ``1.5 * C * sqrt(delta)``.

    The contact is semi-smooth at ``delta = 0``: the force is continuous there but
    the slope jumps from 0 to ``dN/ddelta(0+)``, which is ``0+`` for Hertz and
    finite for a compliant support. Callers assembling a Jacobian must pick a
    side rather than average across the knee.
    """
    if not (depth_m > 0.0) or not math.isfinite(depth_m):
        return 0.0
    if not support_compliance_m_per_n or support_compliance_m_per_n <= 0.0:
        return 1.5 * stiffness_n_m_1p5 * math.sqrt(depth_m)
    if stiffness_n_m_1p5 <= 0.0:
        raise ValueError("contact stiffness must be positive")
    force = series_normal_force(depth_m, stiffness_n_m_1p5, support_compliance_m_per_n)
    if not (force > 0.0):
        return 0.0
    elastic_slope = ((2.0 / 3.0) * (force / stiffness_n_m_1p5) ** (-1.0 / 3.0)
                     / stiffness_n_m_1p5)
    return float(1.0 / (elastic_slope + support_compliance_m_per_n))
