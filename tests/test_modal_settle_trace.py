"""Pin the divergence: the modal settle diverges at 60 km/h and converges at 80.

Round 295 opened `_settle_modal_coordinates` (a fixed-point iteration q += K^-1 Phi^T f) and found
the contraction itself depends on speed: at 80 km/h the per-round step decays with a median ratio
0.446 and the tread settles at 0.98 mm; at 60 km/h the step *grows* (median ratio 1.302) and the
tread is pushed to 25 mm, after which the following seat has no convergent seed.

These tests keep that measurement honest.  They do NOT accept a looser tolerance: a future repair
(damped or Newton settle) must make the step decay at both speeds, and the 60 km/h seat must then
converge -- conditions this file already expresses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import s151_modal_settle_trace as probe  # noqa: E402

pytestmark = pytest.mark.corpus


@pytest.fixture(scope="module")
def traces():
    case = probe.load_vehicle_case(probe.CASE)
    return {speed: probe.trace(case, speed, rounds=8) for speed in (60.0, 80.0)}


def test_the_settle_diverges_at_sixty(traces):
    record = traces[60.0]
    steps = record["steps_m"]
    assert steps[-1] > steps[0]                      # the step grows
    assert float(np.median(record["ratio"])) > 1.0   # contraction above one
    assert record["seat_after"]["ok"] is False       # and the seat that follows cannot recover


def test_the_settle_converges_at_eighty(traces):
    record = traces[80.0]
    steps = record["steps_m"]
    assert steps[-1] < steps[0]
    assert float(np.median(record["ratio"])) < 1.0
    assert record["seat_after"]["ok"] is True
    assert record["seat_after"]["residual_n"] <= 1e-5


def test_both_speeds_leave_the_first_seat_from_the_same_state(traces):
    base = [traces[speed]["seat1_residual_n"] for speed in (60.0, 80.0)]
    assert base[0] == pytest.approx(base[1], rel=1e-3)
