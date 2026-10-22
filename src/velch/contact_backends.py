"""Pluggable contact-geometry backends -- the seam a new algorithm plugs into.

Why this file exists
--------------------
The geometry search is the expensive half of a dynamics evaluation, and every attempt to
make it cheaper has so far been a *different algorithm*, not a tune of the same one:
grid+argmax, strip integral, bounded window, contact map.  Hard-wiring each into
``contact.py`` means the next idea either forks the solver or never lands.  So the contract
lives here and the solver only ever asks for a backend by name.

Contract
--------
A backend answers one question, for one rail body at one pose:

    evaluate(lateral_offset_m, height_offset_m) -> (penetration_m, normal_y, normal_z,
                                                    contact_y_m)

with ``penetration_m`` already clamped at zero, the normal a unit vector in the rail frame,
and ``contact_y_m`` the absolute lateral position of the contact point.  Anything a backend
needs to precompute is built once from a ``closure`` the caller supplies, so this module
does not import ``GraphProfile`` and stays testable against analytic geometry.

Adding a future algorithm
-------------------------
1. Write a factory ``f(closure, **options) -> object with .evaluate(...)``.
2. ``register_backend("my_algo", f)``.
3. Select it with ``make_backend("my_algo", closure, ...)``; nothing else in the solver
   changes, and the acceptance gates applied to it are the ones in
   ``docs/CONTACT_MAP_2026-10-21.md`` (rms/max penetration, contact shift, peak force).

``fallback_required`` states the one rule every approximate backend must obey: at the frog
nose the profile is not smooth across the 20 mm wide, 1.3 mm deep relief, so an
interpolating backend has to hand the pose back to a direct search.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

import numpy as np

from .contact_map import ContactMap, build_map

# A closure takes (lateral_offset_m, height_offset_m) and returns the four quantities.
ContactClosure = Callable[[float, float], tuple[float, float, float, float]]

# Curvature jump per metre above which interpolation is not trusted (the frog nose flips
# curvature within one node spacing; the smooth stretches of the same profile stay orders
# of magnitude below this).
FALLBACK_CURVATURE_JUMP_1_M = 5.0e3


class ContactBackend(Protocol):
    name: str

    def evaluate(self, lateral_offset_m: float,
                 height_offset_m: float) -> tuple[float, float, float, float]: ...


@dataclass(frozen=True)
class DirectBackend:
    """Reference backend: call the closure untouched."""

    closure: ContactClosure
    name: str = "direct"

    def evaluate(self, lateral_offset_m: float,
                 height_offset_m: float) -> tuple[float, float, float, float]:
        return self.closure(lateral_offset_m, height_offset_m)


@dataclass(frozen=True)
class MapBackend:
    """Interpolating backend over a precomputed pose grid."""

    contact_map: ContactMap
    name: str = "map"

    def evaluate(self, lateral_offset_m: float,
                 height_offset_m: float) -> tuple[float, float, float, float]:
        return self.contact_map.evaluate(lateral_offset_m, height_offset_m)


_BUILDERS: dict[str, Callable[..., ContactBackend]] = {
    "direct": lambda closure, **_: DirectBackend(closure),
    "map": lambda closure, offsets_m, heights_m, **_: MapBackend(
        build_map(closure, offsets_m, heights_m)),
}


def register_backend(name: str, factory: Callable[..., ContactBackend]) -> None:
    """Register (or replace) a backend factory under ``name``."""
    if not name:
        raise ValueError("backend name must be non-empty")
    if not callable(factory):
        raise TypeError("backend factory must be callable")
    _BUILDERS[name] = factory


def available_backends() -> tuple[str, ...]:
    return tuple(sorted(_BUILDERS))


def make_backend(name: str, closure: ContactClosure, **options) -> ContactBackend:
    """Instantiate a backend by name; ``options`` go to its factory."""
    try:
        factory = _BUILDERS[name]
    except KeyError as error:
        raise KeyError(
            f"unknown contact backend {name!r}; available: {available_backends()}") from error
    return factory(closure, **options)


def fallback_required(edge_limited: bool, curvature_jump_1_m: float,
                      limit_1_m: float = FALLBACK_CURVATURE_JUMP_1_M) -> bool:
    """Whether an approximating backend must defer to a direct search at this pose."""
    return bool(edge_limited) or abs(float(curvature_jump_1_m)) > float(limit_1_m)


def curvature_jump(rail_z: np.ndarray, rail_y: np.ndarray) -> float:
    """Largest wide-stencil second difference on the rail nodes, 1/m.

    The stencil is ``2 (z[i+1] - 2 z[i] + z[i-1]) / h**2`` with ``h`` the node spacing --
    the same one ``contact._curvature`` uses, and it returns **twice** the second
    derivative.  That factor is deliberate here: the threshold below and this measure are
    read together, and reusing the solver's own stencil keeps the two comparable.  (If the
    solver's ``R*`` ever needs to be an absolute radius, the factor has to be settled in
    ``_curvature`` first -- noted, not changed, because the frozen oracle was calibrated
    with the current scaling.)
    """
    y = np.asarray(rail_y, dtype=float)
    z = np.asarray(rail_z, dtype=float)
    if y.size < 3:
        return 0.0
    width = 0.5 * (y[2:] - y[:-2])
    second = 2.0 * (z[2:] - 2.0 * z[1:-1] + z[:-2]) / (width * width)
    return float(np.max(np.abs(second)))


# --------------------------------------------------------------------------- self-test
def _self_test() -> int:
    from .contact_map import GATE_MAX_DELTA_M, _two_arc_contact

    offsets = np.linspace(-0.008, 0.008, 65)
    heights = np.linspace(-0.0004, 0.0004, 81)
    direct = make_backend("direct", _two_arc_contact)
    mapped = make_backend("map", _two_arc_contact, offsets_m=offsets, heights_m=heights)

    rng = np.random.default_rng(20261021)
    n = 500
    o = rng.uniform(offsets[0], offsets[-1], n)
    h = rng.uniform(heights[0], heights[-1], n)
    worst = 0.0
    for i in range(n):
        worst = max(worst, abs(mapped.evaluate(float(o[i]), float(h[i]))[0]
                               - direct.evaluate(float(o[i]), float(h[i]))[0]))
    ok = worst <= GATE_MAX_DELTA_M

    registered = "probe_backend"
    register_backend(registered, lambda closure, **_: DirectBackend(closure, name="probe_backend"))
    registry_ok = registered in available_backends() and \
        make_backend(registered, _two_arc_contact).evaluate(0.0, 0.0)[0] == 0.0
    unknown = False
    try:
        make_backend("definitely_not_registered", _two_arc_contact)
    except KeyError:
        unknown = True
    guard = fallback_required(True, 0.0) and not fallback_required(False, 1.0)

    print(f"backends={available_backends()}")
    print(f"map vs direct max|dpen| = {worst:.3e} m (limit {GATE_MAX_DELTA_M:.1e}) "
          f"{'PASS' if ok else 'FAIL'}")
    print(f"registry usable={registry_ok} unknown-name raises={unknown} "
          f"fallback guard={guard}")
    return 0 if (ok and registry_ok and unknown and guard) else 1


if __name__ == "__main__":
    raise SystemExit(_self_test())
