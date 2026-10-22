import hashlib

import numpy as np
import pytest

from velch.profiles import (AmbiguousProfileError, GraphProfile, ProfileError,
                            ProfileSeries, Station, graph_from_points, load_profile)


def graph(z: float, identity: str) -> GraphProfile:
    return GraphProfile(np.array([-1.0, 0.0, 1.0]), np.array([z, z, z]),
                        hashlib.sha256(identity.encode()).hexdigest(), identity)


def test_coincident_distinct_profiles_need_explicit_before_after_selection():
    series = ProfileSeries([
        Station(0.0, graph(0.0, "start"), "start"),
        Station(1.0, graph(0.0, "before"), "before"),
        Station(1.0, graph(0.1, "after"), "after"),
        Station(2.0, graph(0.1, "end"), "end"),
    ])
    with pytest.raises(AmbiguousProfileError):
        series.sample(0.5)
    selected = ProfileSeries([
        Station(0.0, graph(0.0, "start"), "start"),
        Station(1.0, graph(0.0, "before"), "before"),
        Station(1.0, graph(0.1, "after"), "after"),
        Station(2.0, graph(0.1, "end"), "end"),
    ], {"1.0": {"before": "before", "after": "after"}})
    assert selected.sample(0.5).selected_ids == ("start", "before")
    assert selected.sample(1.0, direction=1).selected_ids == ("after",)
    assert selected.sample(1.0, direction=-1).selected_ids == ("before",)
    assert selected.sample(1.5).selected_ids == ("after", "end")


def test_envelope_collapse_and_prr_unit_guard(tmp_path):
    points = np.array([[0.0, 0.0], [0.0, 0.2], [1.0, 0.1], [2.0, 0.0]])
    rail = graph_from_points(points, source_sha256="hash", source="memory", surface="rail_top")
    wheel = graph_from_points(points, source_sha256="hash", source="memory", surface="wheel_lower")
    assert rail.collapsed_points == 1
    assert rail.z_m[0] == 0.2
    assert wheel.z_m[0] == 0.0
    file = tmp_path / "small.prr"
    file.write_text("type = 0\nunits.len = 'm'\npoint.begin\n0 0\n0 1\n1 0\n2 0\npoint.end\n")
    assert load_profile(file, file_format="prr", surface="rail_top").collapsed_points == 1
    file.write_text("type = 0\nunits.len = 'mm'\npoint.begin\n0 0\n1 0\n2 0\npoint.end\n")
    with pytest.raises(ProfileError, match="unit"):
        load_profile(file, file_format="prr", surface="rail_top")
