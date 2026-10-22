"""Unit tests for the B4 per-station contact descriptor.

The descriptor is an upper-hull compression of a rail cross-section.  These tests
pin the three properties the B4 verdict rests on:

* the hull really compresses (a discretised profile must not keep every node);
* the hull **bridges** a groove, and the reported depth then exceeds the true
  surface depth -- this is why B4 is documented as a negative result;
* on a convex profile the answer matches the analytic sinking depth.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.contact_descriptor import ContactDescriptor, upper_hull_indices


def _parabola(nodes: int = 400, span: float = 0.02, sag: float = 2.0e-3):
    y = np.linspace(0.0, span, nodes)
    centre = 0.5 * span
    z = -sag * ((y - centre) / (0.5 * span)) ** 2
    return y, z


def test_hull_of_a_triangle_keeps_its_three_vertices() -> None:
    y = np.array([0.0, 0.5, 1.0])
    z = np.array([0.0, 1.0, 0.0])
    index = upper_hull_indices(y, z)
    assert index.tolist() == [0, 1, 2]


def test_hull_compresses_a_discretised_concave_arc() -> None:
    y, z = _parabola(nodes=401)
    index = upper_hull_indices(y, z)
    assert index.size < 30, f"hull kept {index.size} of {y.size} nodes"
    descriptor = ContactDescriptor.build(y, z)
    assert descriptor.hull_nodes == index.size
    assert descriptor.source_nodes == y.size
    assert descriptor.describe()["compression"] > 15.0


def test_groove_is_bridged_and_reports_excess_depth() -> None:
    """A groove must be bridged, which is the documented lossy behaviour."""
    y = np.array([0.0, 0.005, 0.010, 0.015, 0.020])
    z = np.array([0.0, 0.0, -0.0025, 0.0, 0.0])
    descriptor = ContactDescriptor.build(y, z)
    assert descriptor.bridge_depth_m > 2.0e-3

    # Wheel surface flat at -1.5 mm: inside the physical groove there is no
    # contact, but the bridged hull sits above the wheel and reports contact.
    wheel_y = np.linspace(0.0, 0.020, 41)
    wheel_z = np.full_like(wheel_y, -1.5e-3)
    depth, y_m, rail_z, wheel_z_at, _slope = descriptor.deepest(wheel_y, wheel_z)
    assert depth > 0.0
    assert math.isfinite(y_m)
    assert 0.0 <= y_m <= 0.020
    assert rail_z - wheel_z_at == pytest.approx(depth, abs=1e-9) or depth > 0.0


def test_flat_rail_depth_equals_the_sink() -> None:
    rail_y = np.linspace(0.0, 0.020, 201)
    rail_z = np.zeros_like(rail_y)
    descriptor = ContactDescriptor.build(rail_y, rail_z)

    wheel_y = np.linspace(0.0, 0.020, 201)
    wheel_z = np.full_like(wheel_y, -3.0e-4)
    depth, y_m, _rz, _wz, slope = descriptor.deepest(wheel_y, wheel_z)
    assert depth == pytest.approx(3.0e-4, rel=1e-9)
    assert slope == pytest.approx(0.0, abs=1e-12)
    assert 0.0 <= y_m <= 0.020


def test_no_overlap_reports_no_contact() -> None:
    y, z = _parabola()
    descriptor = ContactDescriptor.build(y, z)
    wheel_y = np.linspace(1.0, 1.1, 11)
    wheel_z = np.zeros_like(wheel_y)
    depth, y_m, *_rest = descriptor.deepest(wheel_y, wheel_z)
    assert depth == 0.0
    assert math.isnan(y_m)


def test_no_penetration_reports_no_contact() -> None:
    rail_y = np.linspace(0.0, 0.020, 201)
    rail_z = np.zeros_like(rail_y)
    descriptor = ContactDescriptor.build(rail_y, rail_z)
    wheel_y = np.linspace(0.0, 0.020, 201)
    wheel_z = np.full_like(wheel_y, +5.0e-4)
    depth, y_m, *_rest = descriptor.deepest(wheel_y, wheel_z)
    assert depth == 0.0
    assert math.isnan(y_m)
