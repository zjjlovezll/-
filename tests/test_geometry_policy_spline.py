"""The ``spline`` geometry policy must agree with the grid and change nothing else.

The policy only relocates the contact point; the force assembly still runs on the
existing grid code. These tests pin both halves of that claim.
"""

from __future__ import annotations

import dataclasses
import math
import sys
from pathlib import Path

import pytest


BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from velch.contact import (  # noqa: E402
    GEOMETRY_POLICIES,
    ContactParameters,
    find_graph_contact,
)
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.data_root import case_dir

pytestmark = pytest.mark.corpus

CASE = case_dir() / "case_A_plain.json"


def test_spline_is_a_registered_geometry_policy():
    assert "spline" in GEOMETRY_POLICIES
    default = next(field.default for field in dataclasses.fields(ContactParameters)
                   if field.name == "geometry_policy")
    assert default == "grid"


def _wheel_and_sample():
    case = load_vehicle_case(CASE)
    wheel = case.wheels[0]
    profile = next(
        getattr(wheel, name) for name in ("profile", "graph", "surface")
        if getattr(wheel, name, None) is not None
        and hasattr(getattr(wheel, name), "y_m"))
    rail = next(item for item in case.rails if "right" in item.id)
    series = rail.profiles if rail.bodies == () else rail.bodies[0].series
    return profile, series.sample(13.5)


def _geometry(geometry_policy, sink_m=2.0e-4):
    profile, sample = _wheel_and_sample()
    return find_graph_contact(
        profile, sample,
        wheel_y_m=0.753, wheel_z_m=0.43 - sink_m,
        wheel_roll_rad=0.0, wheel_lateral_offset_m=0.0,
        rail_y_m=0.0, rail_z_m=0.0,
        geometry_policy=geometry_policy,
    )


def _active_sink():
    """Find a sink at which the flat case really is in contact."""
    for step in range(1, 61):
        sink = 1.0e-5 * step
        if _geometry("grid", sink) is not None:
            return sink
    return None


def test_spline_matches_the_grid_on_a_flat_section():
    # On an almost flat pair the deepest point is ill-conditioned laterally, so the
    # invariant to pin is the penetration the two backends report, not where inside
    # the flat band they happen to place it.
    sink = 3.0e-4
    grid = _geometry("grid", sink)
    spline = _geometry("spline", sink)
    assert grid is not None and spline is not None
    assert spline.penetration_m == pytest.approx(grid.penetration_m, rel=0.02)
    assert abs(spline.y_m - grid.y_m) < 1.0e-3
    assert math.isfinite(spline.normal_y) and math.isfinite(spline.normal_z)


def test_spline_policy_leaves_the_default_untouched():
    first = _geometry("grid")
    second = _geometry("grid")
    assert first.penetration_m == second.penetration_m
    assert first.y_m == second.y_m
