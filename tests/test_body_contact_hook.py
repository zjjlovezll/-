"""The per-body contact hook must be inert by default and faithful when installed.

`evaluate` merges a rail's bodies into one response -- that is the force the wheel feels -- but a turnout
switch keeps a stock rail and a blade side by side, and "where does the blade start carrying load" can
only be read per body (`docs/SWITCH_TWO_BODY_2026-10-29.md`, rounds 215-217).  `BODY_CONTACT_HOOK` is the
research read; these tests pin that it changes nothing when unset and that its numbers add up to the
merged response when set.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from velch import vehicle_solver
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics

REPO = Path(__file__).resolve().parents[1]
CASE = REPO.parent / "scratch" / "s52" / "case_two_body_switch.json"

pytestmark = [pytest.mark.corpus, pytest.mark.skipif(not CASE.exists(), reason="two-body case not built")]


@pytest.fixture(scope="module")
def dynamics(tmp_path_factory):
    """The two-body case with a seat on the near-straight approach.

    The corpus case starts at 69 m, where the diverging route is already curved and a vertical seat has
    no solution (`unbalanced branch`), so the seat is taken at 45 m -- the same arrangement the turnout
    acceptance test uses.
    """
    import json

    raw = json.loads(CASE.read_text(encoding="utf-8"))
    raw["run"].update({"x_start_m": 52.0, "seat_x_start_m": 45.0, "duration_s": 0.005})
    raw["vehicle"]["travel_speed_m_s"] = 80.0 / 3.6
    raw.pop("initial_state", None)
    target = tmp_path_factory.mktemp("hook") / "case.json"
    target.write_text(json.dumps(raw), encoding="utf-8")
    case = load_vehicle_case(target)
    engine = VehicleDynamics(case)
    yield engine
    engine.close()


def test_the_hook_is_off_by_default():
    assert vehicle_solver.BODY_CONTACT_HOOK is None


def test_without_the_hook_nothing_is_recorded(dynamics):
    from velch.vehicle_solver import _seat

    case = dynamics.case
    q = np.zeros(dynamics.dimension, dtype=float)
    v = np.zeros(dynamics.dimension, dtype=float)
    seated, _residual = _seat(case, dynamics, q, v)
    _force, before = dynamics.evaluate(0.0, seated, v)
    assert vehicle_solver.BODY_CONTACT_HOOK is None
    assert before  # a merged response per rail still comes back


def test_the_hook_reports_per_body_forces_that_add_up(dynamics):
    from velch.vehicle_solver import _seat

    case = dynamics.case
    q = np.zeros(dynamics.dimension, dtype=float)
    v = np.zeros(dynamics.dimension, dtype=float)
    seated, _residual = _seat(case, dynamics, q, v)

    recorded: dict[str, list[tuple[str, float]]] = {}

    def record(t_s, rail_id, bodies):
        recorded[rail_id] = list(bodies)

    saved = vehicle_solver.BODY_CONTACT_HOOK
    vehicle_solver.BODY_CONTACT_HOOK = record
    try:
        _force, merged = dynamics.evaluate(0.0, seated, v)
    finally:
        vehicle_solver.BODY_CONTACT_HOOK = saved

    assert recorded, "the hook must be called for every rail"
    # The switch zone really has two bodies on the diverging side, so at least one rail reports two.
    assert any(len(bodies) == 2 for bodies in recorded.values())
    for rail_id, bodies in recorded.items():
        total = sum(force for _body_id, force in bodies)
        assert total == pytest.approx(float(merged[rail_id].normal_force_n), rel=1.0e-12, abs=1.0e-6)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
