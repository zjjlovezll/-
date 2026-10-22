"""The backend seam must stay open: named lookup, replaceable factory, guarded fallback."""

from __future__ import annotations

import numpy as np
import pytest

from velch.contact_backends import (
    DirectBackend,
    MapBackend,
    available_backends,
    curvature_jump,
    fallback_required,
    make_backend,
    register_backend,
)
from velch.contact_map import GATE_MAX_DELTA_M, _two_arc_contact


def test_builtin_backends_are_registered():
    names = available_backends()
    assert "direct" in names and "map" in names


def test_direct_backend_passes_the_closure_through():
    backend = make_backend("direct", _two_arc_contact)
    assert isinstance(backend, DirectBackend)
    penetration, _ny, nz, _y = backend.evaluate(0.0, -1.0e-4)
    assert penetration > 0.0
    assert nz == pytest.approx(-1.0)


def test_map_backend_agrees_with_direct_on_smooth_geometry():
    offsets = np.linspace(-0.008, 0.008, 65)
    heights = np.linspace(-0.0004, 0.0004, 81)
    mapped = make_backend("map", _two_arc_contact, offsets_m=offsets, heights_m=heights)
    direct = make_backend("direct", _two_arc_contact)
    assert isinstance(mapped, MapBackend)
    worst = 0.0
    for offset in np.linspace(offsets[0], offsets[-1], 21):
        for height in np.linspace(heights[0], heights[-1], 21):
            worst = max(worst, abs(mapped.evaluate(float(offset), float(height))[0]
                                   - direct.evaluate(float(offset), float(height))[0]))
    assert worst <= GATE_MAX_DELTA_M


def test_unknown_backend_name_lists_the_available_ones():
    with pytest.raises(KeyError) as error:
        make_backend("no_such_algorithm", _two_arc_contact)
    message = str(error.value)
    assert "no_such_algorithm" in message
    assert "direct" in message and "map" in message


def test_registering_a_future_algorithm_overrides_the_lookup(monkeypatch):
    def factory(closure, **_options):
        return DirectBackend(closure, name="my_algorithm_test")

    register_backend("my_algorithm_test", factory)
    backend = make_backend("my_algorithm_test", _two_arc_contact)
    assert isinstance(backend, DirectBackend)
    assert backend.name == "my_algorithm_test"
    assert backend.evaluate(0.0, -2.0e-4)[0] > 0.0


def test_fallback_is_required_at_edges_and_on_curvature_jumps():
    assert fallback_required(True, 0.0)
    assert not fallback_required(False, 1.0)
    assert fallback_required(False, 1.0e4, limit_1_m=5.0e3)


def test_curvature_jump_sees_a_step_but_not_a_crown():
    y = np.linspace(-0.03, 0.03, 601)
    crown = y ** 2 / (2.0 * 0.3)
    # The wide stencil returns twice the second derivative; see the docstring.
    assert curvature_jump(crown, y) == pytest.approx(2.0 / 0.3, rel=0.05)
    stepped = crown.copy()
    stepped[y > 0.01] -= 1.3e-3
    assert curvature_jump(stepped, y) > 1.0e3
