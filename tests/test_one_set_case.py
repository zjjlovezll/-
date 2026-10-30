"""M1: the four pieces have to live in one case, not four.

Before this test the repository had no case that combined all of them: the packaged turnout cases
carried real turnout geometry on a compliant track but a rigid-wheelset 35-coordinate car, the
flexible-wheelset example carried 12 synthetic stations, and the most complete car
(``CRH380A_M_axlebox``, 86 coordinates, eight axlebox bodies) had no case at all.

These tests pin the assembly so a later edit cannot quietly drop a piece: the dimension arithmetic,
the body census, the modal count, the speed the case states, and the fact that the blade still
starts 14.94 mm below the stock (a builder that re-injects the lowering would show up here).
"""
from __future__ import annotations

import pathlib

import pytest

from velch.topology import topology_of
from velch.vehicle import load_vehicle_case

pytestmark = pytest.mark.corpus

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"


@pytest.fixture(scope="module")
def loaded():
    assert CASE.exists(), f"missing the one-set case: {CASE}"
    return load_vehicle_case(CASE)


def test_the_vehicle_is_the_complete_car_not_a_reduced_copy(loaded) -> None:
    """86 coordinates, fifteen bodies, eight of them axleboxes."""
    topology = topology_of(loaded.topology, loaded.vehicle)
    kinds: dict[str, int] = {}
    for body in topology.bodies:
        kinds[body.kind] = kinds.get(body.kind, 0) + 1
    assert topology.body_dimension == 86
    assert len(topology.bodies) == 15
    assert kinds.get("axlebox") == 8, f"expected eight axlebox bodies, got {kinds}"
    assert kinds.get("wheelset") == 4 and kinds.get("bogie") == 2 and kinds.get("carbody") == 1


def test_all_four_wheelsets_carry_a_flexible_modal_set(loaded) -> None:
    modes = loaded.wheel_modes
    assert modes is not None, "the case lost its flexible wheelsets"
    assert sorted(modes) == [0, 1, 2, 3]
    assert [len(item.modes) for _, item in sorted(modes.items())] == [33, 33, 33, 33]


def test_the_dimension_is_vehicle_plus_track_plus_modes(loaded) -> None:
    """234 = 86 car + 16 track (8 rails x 2) + 132 modal (4 x 33)."""
    topology = topology_of(loaded.topology, loaded.vehicle)
    modal = sum(len(item.modes) for item in (loaded.wheel_modes or {}).values())
    track = 2 * len(loaded.rails)
    assert len(loaded.initial_q) == topology.body_dimension + track + modal == 234
    assert track == 16 and modal == 132
    assert len(loaded.initial_v) == 234


def test_the_case_states_the_running_speed_rather_than_inheriting_the_line_speed(loaded) -> None:
    """The axlebox car carries its own 350 km/h; a turnout run must not borrow it."""
    assert loaded.speed_schedule is not None and loaded.speed_schedule.is_constant
    assert loaded.vehicle.travel_speed_m_s == pytest.approx(80.0 / 3.6, rel=0.0, abs=1e-12)


def test_the_turnout_geometry_survives_the_assembly(loaded) -> None:
    """Right side keeps stock + blade + frog per axle; the blade still starts 14.94 mm down."""
    right = [rail for rail in loaded.rails if rail.id.endswith("_right")]
    assert len(right) == 4
    for rail in right:
        assert [body.id for body in rail.contact_bodies] == ["stock", "blade", "frog"]
    stock = next(rail for rail in right if rail.id == "axle1_right")
    body = {item.id: item for item in stock.contact_bodies}["blade"]
    tip = body.series.sample(50.578, 1.0)
    stock_sample = stock.contact_bodies[0].series.sample(50.578, 1.0)
    gap = float(tip.profile.z_m.max() - stock_sample.profile.z_m.max())
    assert gap == pytest.approx(-14.94e-3, abs=0.2e-3), f"blade tip gap {gap * 1e3:.3f} mm"
