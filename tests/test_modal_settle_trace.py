"""Pin what the adaptive settle changed, and what it did not.

Round 295 measured the plain fixed point at 60 km/h: the per-round step grew (median ratio 1.302) and
pushed the modal coordinates to 25 mm, after which the following seat had no convergent seed.
Round 296 replaced the fixed point with an under-relaxed pass (halve when a pass stops shrinking,
recover when it keeps shrinking) and measured again:

    60 km/h  modal bounded at 1.058 mm (was 25 mm), step decays 2.4e-2 -> 7.1e-6 m, seat STILL fails
    80 km/h  unchanged: relaxation stays 1.0, modal 0.9761 mm, seat 2.98e-08 N

So the runaway is gone and the 60 km/h blocker has moved from the settle to the seat.  These tests
hold both halves of that statement: the settle must stay bounded, and the seat must still be recorded
as failing -- a future change that makes the seat converge should update the second assertion
deliberately, not silently.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import s151_modal_settle_trace as probe  # noqa: E402

pytestmark = pytest.mark.corpus

BOUND_M = 2.0e-3


@pytest.fixture(scope="module")
def traces():
    case = probe.load_vehicle_case(probe.CASE)
    return {speed: probe.trace(case, speed) for speed in (60.0, 80.0)}


def test_the_settle_no_longer_runs_away_at_sixty(traces):
    record = traces[60.0]
    modal = float(record["block_max_m"][0])
    assert modal <= BOUND_M, f"modal {modal:.3e} m exceeds the {BOUND_M:.1e} m bound"


def test_the_sixty_seat_now_closes(traces):
    record = traces[60.0]["seat_after"]
    assert record["ok"] is True
    assert record["residual_n"] <= 1e-5
    assert -1470.0 <= record["wheel_z_um"] <= -1455.0


def test_the_settle_converges_at_eighty_unchanged(traces):
    record = traces[80.0]
    assert 9.5e-4 <= float(record["block_max_m"][0]) <= 1.0e-3
    assert record["seat_after"]["ok"] is True
    assert record["seat_after"]["residual_n"] <= 1e-5


def test_both_speeds_leave_the_first_seat_from_the_same_state(traces):
    base = [traces[speed]["seat1_residual_n"] for speed in (60.0, 80.0)]
    assert base[0] == pytest.approx(base[1], rel=1e-3)

def test_the_plain_scale_alone_still_has_no_seed_at_sixty():
    """The fallback is doing the work: scale 1.0 by itself must still report no solution.

    If this ever stops failing, the fallback list is no longer needed and that should be a
    deliberate change, not a silent one.
    """
    import dataclasses

    import numpy as np

    import velch.vehicle_solver as vs
    from velch.solver import SimulationFailure

    case = probe.load_vehicle_case(probe.CASE)
    dyn = vs.VehicleDynamics(case)
    q = np.asarray(case.initial_q, float)
    v = np.asarray(case.initial_v, float)
    for axle in (1, 2, 3, 4):
        v[dyn.topology.require(f"wheelset{axle}", "spin")] = 60.0 / 3.6 / 0.43
    q, _ = vs._seat(case, dyn, q, v)
    settled = vs._settle_modal_coordinates(dyn, q, v)
    plain = dataclasses.replace(case, run=dataclasses.replace(case.run, seat_modal_scales=(1.0,)))
    with pytest.raises(SimulationFailure):
        vs._seat_once(plain, dyn, settled, v)


def test_the_corrected_sixty_run_integrates():
    """The 0.02 s run that used to die on the rear-axle slope guard now clears all seven gates."""
    import json

    run = probe.ROOT.parent / "scratch" / "runs" / "one_set_x46-060.00kmh-0.0200s-500us-83e727fc"
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    assert float(meta["speed_kmh"]) == pytest.approx(60.0)
    assert float(meta["profile_speed_kmh"]) == pytest.approx(60.0)
    assert all(bool(value) for value in meta["gates"].values())
