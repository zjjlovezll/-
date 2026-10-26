"""The even share belongs to a wheel, not to a declared rail.

Two opposite mistakes met here.  Dividing the weight by ``len(case.rails)`` put the accept limit
only 2.8 % above the correct solution on a twelve-rail turnout case (B036).  Dividing by eight
patches and then demanding that *every* declared rail carry load is the opposite error: no
multi-rail case can ever satisfy it, because a switch rail standing above the running surface
carries nothing, and at a diverging point two rails can share one wheel (B038).

So the patches are grouped by wheel — same axle and same side — and the comparison is made per
wheel.  These tests pin the grouping, because everything downstream (seed scoring, the starved
criterion, the failure message) now depends on it.
"""
from __future__ import annotations

from types import SimpleNamespace

from velch.vehicle_solver import _load_per_wheel, _wheel_of


def _rail(axle: int, side: str, template: str) -> SimpleNamespace:
    return SimpleNamespace(axle_index=axle, id=f"axle{axle + 1}_{side}_{template}",
                           template_id=f"{side}.{template}")


def test_the_same_wheel_splits_its_load_between_two_rails():
    rails = [_rail(0, "left", "stock"), _rail(0, "left", "switch")]
    loads = [30.0e3, 29.0e3]
    per_wheel = _load_per_wheel(rails, loads)
    assert per_wheel == {(0, "left"): 59.0e3}


def test_eight_wheels_stay_eight_however_many_rails_a_turnout_declares():
    rails = []
    for axle in range(4):
        for side in ("left", "right"):
            rails.append(_rail(axle, side, "stock"))
            if axle in (0, 1):
                rails.append(_rail(axle, side, "switch"))
    assert len(rails) == 12
    per_wheel = _load_per_wheel(rails, [1.0e3] * len(rails))
    assert len(per_wheel) == 8
    assert set(per_wheel) == {(axle, side) for axle in range(4) for side in ("left", "right")}


def test_left_and_right_are_different_wheels():
    rails = [_rail(2, "left", "stock"), _rail(2, "right", "stock")]
    per_wheel = _load_per_wheel(rails, [59.0e3, 60.0e3])
    assert per_wheel[(2, "left")] == 59.0e3
    assert per_wheel[(2, "right")] == 60.0e3


def test_the_side_is_read_from_id_when_the_template_id_is_ambiguous():
    rail = SimpleNamespace(axle_index=1, id="axle2_right_main", template_id="R74")
    assert _wheel_of(rail) == (1, "right")


def test_a_rail_without_a_side_falls_back_to_its_template_id():
    rail = SimpleNamespace(axle_index=0, id="left0", template_id="left")
    assert _wheel_of(rail) == (0, "left")
