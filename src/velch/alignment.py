"""Where the design line is, and which way it bends -- one object, one sign convention.

The measured history of the curved route is a history of the same quantity written down in three
places that were never bound to each other:

* the station table / ``path`` turns towards ``+y`` (``y = s^2 / (2R)``, centre at ``+y``);
* the equivalent-straight body force added ``+m v^2/R`` to ``+y`` under the comment "outward is
  ``+y``" -- which, on that line, pushes the vehicle *inward*;
* the creep term ``-kappa v lever_y`` had a handedness that was only implicit.

Flipping one of them at a time cannot produce a steady state: measured on R = 1100 m at 80 km/h,
0.34 s gave a net lateral force of -78.1 % of ``m v^2/R`` with one sign and +69.1 % with the
other, and 0.60 s then reached +157.2 % -- the trajectory diverged either way.

This module is the single statement they are all derived from.  Conventions, stated once:

* ``+y`` is to the right of the direction of travel (``paths.py``), so ``kappa > 0`` means the
  centre of curvature sits at ``+y`` and the route turns towards ``+y``;
* a contact at lateral offset ``n`` (``+y`` positive) then travels ``v (1 - kappa n)`` per second,
  which is what ``contact.slip_x`` implements -- so the creep handedness is the *reference*;
* in the vehicle's own frame the inertia force points away from the centre, i.e. towards ``-y``
  when ``kappa > 0``: ``F_y = -m v^2 kappa``;
* when the track is canted, the rail on the *outside* of the curve is raised.  With ``kappa > 0``
  the outside is the ``-y`` side, so the gravity component along the cant plane points towards
  ``+y``: ``F_y = +m g sin(theta)`` with ``sin(theta) > 0`` meaning "the ``-y`` rail is higher".

The legacy force route (``curve_radius_m`` with straight rails and no line) predates this object.
Its convention is the mirror image -- centre at ``-y`` -- and it is kept *bit-identical* here
because every archived number was measured with it; ``from_radius`` marks that explicitly instead
of pretending the two agree.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

__all__ = ["Alignment", "alignment_for"]


@dataclass(frozen=True)
class Alignment:
    """Signed curvature of the design line, with the force convention derived from it."""

    #: ``1/m``: positive when the centre of curvature is at ``+y``.
    curvature_1_per_m: float = 0.0
    #: The legacy route's radius, kept so the archived arithmetic (a division) is reproduced.
    radius_m: float | None = None
    #: Stations of the line, ``None`` for a constant-curvature or straight route.
    stations_s_m: tuple[float, ...] = ()
    #: Station-wise curvature when the line is not a single radius.
    curvature_table: tuple[float, ...] = ()
    #: The legacy equivalent-straight route: force convention mirrored, kept bit-identical.
    legacy_equivalent_straight: bool = False

    # -- constructors ----------------------------------------------------------------------
    @classmethod
    def straight(cls) -> "Alignment":
        return cls()

    @classmethod
    def from_radius(cls, radius_m: float) -> "Alignment":
        """The legacy equivalent-straight route: ``+m v^2/R`` towards ``+y``, i.e. centre at -y."""
        if not math.isfinite(radius_m) or radius_m <= 0.0:
            raise ValueError(f"curve radius must be a positive finite value, got {radius_m!r}")
        return cls(curvature_1_per_m=1.0 / float(radius_m), radius_m=float(radius_m),
                   legacy_equivalent_straight=True)

    @classmethod
    def from_path(cls, path) -> "Alignment":
        """Curvature of a ``PathTrack``, taken from its own stations (piecewise constant)."""
        stations = tuple(float(s) for s in path.stations_s_m)
        offsets = np.asarray(path.y_m, dtype=float)
        if len(stations) < 3:
            return cls()
        mids = np.array([0.5 * (stations[i] + stations[i + 1]) for i in range(len(stations) - 1)])
        slopes = np.diff(offsets) / np.diff(np.asarray(stations, dtype=float))
        curvature = tuple(float(value) for value in np.diff(slopes) / np.diff(mids))
        if not all(math.isfinite(value) for value in curvature):
            raise ValueError("path produced a non-finite curvature")
        return cls(
            curvature_1_per_m=float(np.median(curvature)),
            stations_s_m=tuple(float(value) for value in mids[1:]),
            curvature_table=curvature,
        )

    # -- evaluation ------------------------------------------------------------------------
    @property
    def has_line(self) -> bool:
        """True when the curvature came from an actual line rather than a legacy convention."""
        return bool(self.curvature_table)

    def curvature_at(self, station_m: float) -> float:
        if not self.curvature_table:
            return self.curvature_1_per_m
        return float(np.interp(float(station_m), self.stations_s_m, self.curvature_table))

    def lateral_force_n(self, mass_kg: float, speed_m_s: float, gravity_m_s2: float,
                        sin_theta: float, *, station_m: float = 0.0) -> float:
        """The lateral force this line demands, in the one convention the creep law uses."""
        speed = abs(float(speed_m_s))
        if self.legacy_equivalent_straight:
            # Centre at -y: the inertia force is +y and the cant term subtracts.  This is the
            # expression every archived curved case was measured with, kept in this order so the
            # floating-point result is unchanged.
            assert self.radius_m is not None
            return float(mass_kg) * (speed * speed / self.radius_m
                                     - gravity_m_s2 * sin_theta)
        if self.has_line:
            # Derived from the line itself: inertia force away from the centre at +y, and the
            # raised rail (outside, -y) pushes the body towards +y.
            return (float(mass_kg) * (gravity_m_s2 * sin_theta
                                      - speed * speed * self.curvature_at(station_m)))
        return 0.0


def alignment_for(case) -> Alignment:
    """The line a case rides on: its path table if it has one, else the legacy radius."""
    path = getattr(case, "path", None)
    if path is not None:
        line = Alignment.from_path(path)
        if line.has_line:
            return line
    radius = getattr(case.run, "curve_radius_m", None)
    if radius:
        return Alignment.from_radius(float(radius))
    return Alignment.straight()
