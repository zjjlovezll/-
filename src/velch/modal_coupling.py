"""Apply a force that acts at the tread to the wheelset's modal coordinates.

The modal block in :mod:`velch.wheel_modes` knows how a modal displacement pushes back
(``K q + C v``), but nothing yet pushes *in*.  A force applied at a point of the tread has to
be projected onto the mode shapes, ``Q_i = phi_i(x) . f``, or the modes sit at zero forever —
which is exactly what the first flexible run showed (``max |q| = 0.000e+00``).

The projection is done through a Gaussian kernel over the tread-ring nodes that carry the
shapes.  Two properties make this a physical map rather than a smoothing trick, and both are
tested:

* the weights sum to one, so a rigid translation of the whole ring passes the force through
  unchanged (a force cannot be created or lost by the projection);
* the same weights are used to reconstruct the displacement at the point, so virtual work
  closes: ``Q . q == f . d(x)`` for every ``q``.  Weighting the force one way and reading the
  displacement another would silently break energy conservation, and a peak force would not
  show it.

What this module deliberately does not do yet: it does not deform the contact geometry.  The
contact is still searched on the undeformed tread (that is S8-3), so a force is applied at the
nominal tread point and the response is linear in it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .wheel_modes import ModeError, ModeSet


@dataclass(frozen=True)
class TreadRing:
    """One wheel's tread nodes and the shapes that move them.

    ``side`` is the sign of this wheel's CAD lateral coordinate: the vehicle convention in this
    codebase is *left = negative y* (``wheels[].lateral_offset_m`` is −0.75 for "L"), and the
    CAD wheel planes are at y = ±0.7359 m.
    """

    side: int
    nodes: np.ndarray
    shapes: np.ndarray
    radius_m: float
    sigma_m: float = 0.04

    def __post_init__(self) -> None:
        if self.side not in (-1, 1):
            raise ModeError(f"side must be -1 or +1, got {self.side!r}")
        if self.nodes.ndim != 2 or self.nodes.shape[1] != 3:
            raise ModeError(f"tread nodes must be (n, 3), got {self.nodes.shape}")
        if self.shapes.ndim != 3 or self.shapes.shape[1:] != (self.nodes.shape[0], 3):
            raise ModeError(f"shapes must be (m, {self.nodes.shape[0]}, 3), got {self.shapes.shape}")
        if self.sigma_m <= 0.0:
            raise ModeError(f"kernel width must be positive, got {self.sigma_m!r}")

    @property
    def n_modes(self) -> int:
        return self.shapes.shape[0]

    @property
    def plane_y_m(self) -> float:
        """Lateral position of this wheel, taken from the geometry rather than assumed."""
        return float(np.median(self.nodes[:, 1]))

    @property
    def centre(self) -> np.ndarray:
        """Centre of the tread ring, i.e. the wheel centre, in the CAD frame.

        The shapes are stored in the CAD assembly frame, whose origin is *not* the wheelset
        centre: this wheel's ring sits at x ≈ −1.25 m (the axle is modelled about x = −1250 mm).
        A contact point placed at x = 0 would land 1.25 m away and the kernel would pick up
        whatever happened to be nearest, so the centre has to be measured.
        """
        return np.array([float(np.median(self.nodes[:, 0])), self.plane_y_m,
                         float(np.median(self.nodes[:, 2]))])

    @classmethod
    def from_modes(cls, modes: ModeSet, side: int, sigma_m: float = 0.04) -> "TreadRing":
        if not modes.has_shapes or modes.nodes is None or modes.shapes is None:
            raise ModeError(
                "a contact force cannot be projected without mode shapes: load a set with "
                "'shapes' and 'nodes' (e.g. vehicles/modes/CRH3C_wheelset_fe.json)"
            )
        if side not in (-1, 1):
            raise ModeError(f"side must be -1 or +1, got {side!r}")
        mask = modes.nodes[:, 1] > 0.0 if side > 0 else modes.nodes[:, 1] < 0.0
        if not np.any(mask):
            raise ModeError(
                f"no tread nodes on the {'positive' if side > 0 else 'negative'} y side: the "
                "shapes look single-wheel"
            )
        return cls(side=side, nodes=modes.nodes[mask], shapes=modes.shapes[:, mask, :],
                   radius_m=modes.radius_m, sigma_m=sigma_m)

    def contact_point(self, lateral_m: float = 0.0, penetration_m: float = 0.0) -> np.ndarray:
        """Tread point under the contact, at a given lateral offset from the wheel plane.

        ``lateral_m`` is where the contact actually sits relative to the wheel centre, so a
        flange contact reads the tread above the flange root rather than above the wheel
        centre.  The vertical position still assumes the point sits at the bottom of the ring:
        with a rolled wheel the lowest tread point is not exactly there, which is the next
        order of the same approximation (see the module docstring).
        """
        centre = self.centre
        return np.array([centre[0], centre[1] + float(lateral_m),
                         centre[2] - self.radius_m + float(penetration_m)])

    def bottom_point(self, penetration_m: float = 0.0) -> np.ndarray:
        """Tread point under the wheel centre — where the normal force of a level track acts."""
        return self.contact_point(0.0, penetration_m)

    def deformation(self, q, lateral_m: float = 0.0, penetration_m: float = 0.0,
                    span_m: float = 0.01) -> tuple[float, float]:
        """Tread displacement and its lateral slope at the contact point.

        Both come from the same kernel and the same shapes: the displacement is what changes the
        depth, and the slope is what turns the contact normal (Gao & Dai's contact-line method
        takes the normal *after* deformation, and the slope is the only part of that rotation a
        tread ring can supply).  ``span_m`` is the finite-difference step along the ring; 10 mm
        is a tenth of the kernel width, so it reads the ring's own gradient rather than noise.
        """
        q = np.asarray(q, dtype=float)
        here = float(self.displacement(self.contact_point(lateral_m, penetration_m), q)[2])
        right = self.contact_point(lateral_m + span_m, penetration_m)
        left = self.contact_point(lateral_m - span_m, penetration_m)
        slope = (float(self.displacement(right, q)[2])
                 - float(self.displacement(left, q)[2])) / (2.0 * span_m)
        return here, slope

    def weights(self, point) -> np.ndarray:
        """Kernel weights over the nodes, normalised to sum to one."""
        point = np.asarray(point, dtype=float).reshape(3)
        squared = ((self.nodes - point) ** 2).sum(axis=1)
        w = np.exp(-0.5 * squared / (self.sigma_m ** 2))
        total = float(w.sum())
        if total <= 0.0:
            raise ModeError(f"the kernel found no tread node near {tuple(point)}")
        return w / total

    def generalised_force(self, point, force) -> np.ndarray:
        """``Q_i = sum_a w_a phi_i(a) . f`` — the modal force of ``f`` applied at ``point``."""
        w = self.weights(point)
        force = np.asarray(force, dtype=float).reshape(3)
        return (self.shapes * w[None, :, None]).sum(axis=1) @ force

    def displacement(self, point, q) -> np.ndarray:
        """Tread displacement at ``point`` for modal coordinates ``q`` (same weights)."""
        w = self.weights(point)
        q = np.asarray(q, dtype=float).reshape(self.n_modes)
        # sum_i q_i phi_i at each node, then the same kernel over the nodes: broadcasting
        # q against the mode axis first is what keeps this identical to the force map's weights
        moved = (q[:, None, None] * self.shapes).sum(axis=0)
        return (w[:, None] * moved).sum(axis=0)


@dataclass(frozen=True)
class ModalContact:
    """Routes a contact force into the right axle's modal block."""

    rings: "dict[int, TreadRing]"
    offsets: "dict[int, int]"

    def __post_init__(self) -> None:
        # rings are keyed by wheel side (-1/+1) and offsets by axle, so these are different
        # key spaces on purpose; only the sizes have to agree
        if not self.rings:
            raise ModeError("a contact coupling needs at least one tread ring")
        sizes = {ring.n_modes for ring in self.rings.values()}
        if len(sizes) != 1:
            raise ModeError(f"every ring must carry the same mode count, got {sorted(sizes)}")
        if any(int(start) < 0 for start in self.offsets.values()):
            raise ModeError(f"modal block offsets must be non-negative, got {self.offsets}")

    @property
    def n_modes(self) -> int:
        return next(iter(self.rings.values())).n_modes

    def generalised(self, axle: int, side: int, point, force) -> np.ndarray:
        """Modal force on ``axle`` from ``force`` applied at ``point`` on wheel ``side``."""
        ring = self.rings.get(side)
        if ring is None:
            raise ModeError(f"no tread ring for side {side!r}; built sides are {sorted(self.rings)}")
        return ring.generalised_force(point, force)

    def block(self, axle: int) -> slice:
        try:
            start = self.offsets[axle]
        except KeyError:
            raise ModeError(f"no modal block for axle {axle!r}; built axles are "
                            f"{sorted(self.offsets)}") from None
        return slice(start, start + self.n_modes)
