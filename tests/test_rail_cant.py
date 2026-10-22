"""Rail cant (轨底坡) as a profile rotation about the crown centre.

Physics under test:

* rotating a flat surface by ``theta`` about a point changes its elevation by
  ``theta * (y - y_pivot)`` (small-angle), so a 1:40 rail cant must shift the
  running surface by ``((y - y_pivot) / 40)`` — 0.875 mm across a 35 mm half head,
  not 35 mm;
* rotating about the **gauge face** (``y_pivot = 0`` when the crown is at
  ``y = +35 mm``) would raise the whole crown by ``35/40 = 0.875 mm``, which is
  the bug that once produced a 1930 kN normal force;
* rotating about the **crown centre** keeps the crown height, so the static wheel
  load must stay unchanged.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.profiles import GraphProfile, graph_from_points

CANT = math.atan(1.0 / 40.0)


def flat_plate(half_width_m: float = 0.035, step_m: float = 5.0e-4) -> np.ndarray:
    y = np.arange(-half_width_m, half_width_m + 0.5 * step_m, step_m)
    return np.column_stack([y, np.zeros_like(y)])


def test_zero_roll_reproduces_the_unrotated_profile() -> None:
    plate = flat_plate()
    plain = graph_from_points(plate, source_sha256="x", source="synthetic",
                              surface="rail_top")
    rolled = graph_from_points(plate, source_sha256="x", source="synthetic",
                               surface="rail_top", roll_rad=0.0,
                               roll_pivot_y_m=0.0, roll_pivot_z_m=0.0)
    assert np.allclose(plain.y_m, rolled.y_m, atol=0, rtol=0)
    assert np.allclose(plain.z_m, rolled.z_m, atol=0, rtol=0)


def test_cant_about_the_crown_centre_tilts_the_surface_by_one_in_forty() -> None:
    # Crown centre at y = +0.035 m, z = 0: the running surface centre keeps its height.
    plate = flat_plate(half_width_m=0.070)
    profile = graph_from_points(plate, source_sha256="x", source="synthetic",
                                surface="rail_top", roll_rad=CANT,
                                roll_pivot_y_m=0.035, roll_pivot_z_m=0.0)
    # The whole surface must be the straight line z = (y - 0.035)/40.
    expected = (profile.y_m - 0.035) / 40.0
    assert np.allclose(profile.z_m, expected, atol=2e-6)
    assert float(np.interp(0.035, profile.y_m, profile.z_m)) == pytest.approx(0.0, abs=2e-6)
    # 35 mm outboard of the pivot the surface is 0.875 mm higher, inboard it is lower.
    assert float(np.interp(0.0698, profile.y_m, profile.z_m)) == pytest.approx(
        0.0348 / 40.0, abs=2e-6)
    assert float(np.interp(0.0002, profile.y_m, profile.z_m)) == pytest.approx(
        -0.0348 / 40.0, abs=2e-6)
    gradient = np.gradient(profile.z_m, profile.y_m)
    assert float(np.median(gradient)) == pytest.approx(1.0 / 40.0, rel=2e-3)


def test_cant_about_the_gauge_face_raises_the_crown_and_is_the_known_bug() -> None:
    """Guard: pivoting at the gauge face produces the 0.875 mm offset."""

    plate = flat_plate(half_width_m=0.070)
    profile = graph_from_points(plate, source_sha256="x", source="synthetic",
                                surface="rail_top", roll_rad=CANT,
                                roll_pivot_y_m=0.0, roll_pivot_z_m=0.0)
    raised = float(profile.z_at(0.035))
    assert raised == pytest.approx(0.035 / 40.0, abs=2e-6)
    # That is 17x the static Hertzian penetration (65.5 um) and cannot be a
    # modelling detail, which is why the pivot is part of the case contract.
    assert raised > 10 * 65.5e-6


def test_roll_requires_finite_parameters() -> None:
    plate = flat_plate()
    with pytest.raises(ValueError):
        graph_from_points(plate, source_sha256="x", source="synthetic",
                          surface="rail_top", roll_rad=float("nan"))


def test_rotation_preserves_the_source_hash_and_point_count() -> None:
    plate = flat_plate()
    profile = graph_from_points(plate, source_sha256="abc", source="synthetic",
                                surface="rail_top", roll_rad=CANT,
                                roll_pivot_y_m=0.035)
    reference = graph_from_points(plate, source_sha256="abc", source="synthetic",
                                  surface="rail_top")
    assert isinstance(profile, GraphProfile)
    assert profile.source_sha256 == "abc"
    assert profile.y_m.shape == reference.y_m.shape
