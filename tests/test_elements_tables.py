"""Tests for the bump stop's C1 ramp and the table-driven element."""
from __future__ import annotations

import pytest

from velch.elements import BumpStopLaw, TableLaw, build, parse
from velch.topology import TopologyError


def test_the_ramp_is_off_by_default() -> None:
    plain = BumpStopLaw(stiffness_n_m=1.0e6, gap_m=0.002)
    assert plain.transition_m == 0.0
    assert plain.force(-0.003, 0.0) == pytest.approx(-1000.0)
    assert plain.stiffness(-0.0020001) == pytest.approx(1.0e6)


def test_the_ramp_makes_force_and_slope_continuous() -> None:
    law = BumpStopLaw(stiffness_n_m=1.0e6, gap_m=0.002, transition_m=0.001)
    edge = 0.002 + 0.001
    below = law.force(-edge + 1e-9, 0.0)
    above = law.force(-edge - 1e-9, 0.0)
    assert below == pytest.approx(above, abs=1e-2)
    assert law.stiffness(-edge + 1e-9) == pytest.approx(1.0e6, rel=1e-6)
    assert law.stiffness(-edge - 1e-9) == pytest.approx(1.0e6, rel=1e-6)
    # The ramp consumes kT/2 of force, so the linear branch is shifted by exactly that much.
    assert law.force(-(edge), 0.0) == pytest.approx(-500.0)
    assert law.force(-(0.002 + 0.002), 0.0) == pytest.approx(-1500.0)


def test_the_ramp_energy_still_matches_the_force() -> None:
    law = BumpStopLaw(stiffness_n_m=1.0e6, gap_m=0.002, transition_m=0.001)
    step = 1e-9
    for travel in (0.0002, 0.0009, 0.0015, 0.004):
        extension = -0.002 - travel
        slope = ((law.potential(extension + step) - law.potential(extension - step))
                 / (2.0 * step))
        assert slope == pytest.approx(law.force(extension, 0.0), rel=1e-6, abs=1e-3)


def test_a_table_interpolates_and_clamps() -> None:
    law = TableLaw(points=((0.0, 0.0), (0.001, 1000.0), (0.002, 3000.0)))
    assert law.force(0.0015, 0.0) == pytest.approx(2000.0)
    assert law.stiffness(0.0015) == pytest.approx(2.0e6)
    assert law.force(0.005, 0.0) == pytest.approx(3000.0)   # clamped
    assert law.stiffness(0.005) == 0.0                      # trend unknown out there
    assert law.force(-0.001, 0.0) == pytest.approx(0.0)
    assert law.stiffness(-0.001) == 0.0


def test_a_table_can_carry_a_rate_curve_too() -> None:
    law = TableLaw(points=((0.0, 0.0), (0.01, 500.0)),
                   rate_points=((0.0, 0.0), (0.05, 2000.0), (0.2, 2750.0)))
    assert law.force(0.0, 0.1) == pytest.approx(2250.0)  # rate curve only, at zero extension
    assert law.damping(0.1) == pytest.approx(5000.0)
    assert law.stiffness(0.005) == pytest.approx(5.0e4)


def test_the_table_energy_matches_the_force() -> None:
    law = TableLaw(points=((0.0, 0.0), (0.001, 1000.0), (0.003, 5000.0)))
    step = 1e-9
    for extension in (0.0005, 0.002, 0.0029):
        slope = ((law.potential(extension + step) - law.potential(extension - step))
                 / (2.0 * step))
        assert slope == pytest.approx(law.force(extension, 0.0), rel=1e-6, abs=1e-3)


def test_a_table_must_be_sorted_and_have_two_points() -> None:
    with pytest.raises(ValueError, match="sorted"):
        TableLaw(points=((0.002, 3000.0), (0.0, 0.0)))
    with pytest.raises(ValueError, match="at least two"):
        TableLaw(points=((0.0, 0.0),))


def test_a_table_element_is_parsed_and_built_from_data() -> None:
    spec = parse({"kind": "force_table", "name": "air_spring", "from": {"body": "a"},
                  "direction": [0, 0, 1],
                  "points": [[0.0, 0.0], [0.01, 4000.0]],
                  "rate_points": [[0.0, 0.0], [0.1, 500.0]]})
    assert spec.parameters["points"] == ((0.0, 0.0), (0.01, 4000.0))
    assert spec.parameters["rate_points"] == ((0.0, 0.0), (0.1, 500.0))


def test_a_table_with_one_point_is_refused_with_units() -> None:
    with pytest.raises(TopologyError, match=r"force_table.*two 'points'"):
        parse({"kind": "force_table", "name": "t", "from": {"body": "a"},
               "points": [[0.0, 0.0]]})


def test_an_unsorted_table_in_a_model_is_refused() -> None:
    with pytest.raises(TopologyError, match="sorted"):
        parse({"kind": "force_table", "name": "t", "from": {"body": "a"},
               "points": [[0.01, 1.0], [0.0, 0.0]]})


def test_a_bump_stop_element_carries_its_ramp() -> None:
    spec = parse({"kind": "bump_stop", "name": "stop", "from": {"body": "a"},
                  "stiffness": 8.0e5, "gap_m": 0.002, "transition_m": 0.0005})
    assert spec.parameters["transition_m"] == pytest.approx(0.0005)
