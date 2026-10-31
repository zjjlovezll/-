"""Pin the fact that the corrected 60 km/h case fails before the first frame.

Round 293 fixed the speed label (B052).  Round 294 then found that the corrected 60 km/h
case dies in the *second* seat -- the one after the first modal settle -- while the same
geometry at 80 km/h walks the whole chain.  These tests pin that reading so a future change
cannot quietly "fix" it by loosening a tolerance: the failure must stay a failure, and the
80 km/h chain must keep converging to the centred branch.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import s150_seat_after_settle as probe  # noqa: E402

pytestmark = pytest.mark.corpus


@pytest.fixture(scope="module")
def chains():
    case = probe.load_vehicle_case(probe.CASE)
    return {speed: probe.chain(case, speed) for speed in (60.0, 80.0)}


def test_the_corrected_sixty_fails_before_the_first_frame(chains):
    record = chains[60.0]
    assert record["ok"] is False
    assert "preload equilibrium failed" in record["error"]
    # it must die *after* the first seat and *at* the seat that follows the settle
    stages = [s["stage"] for s in record["stages"]]
    assert stages == ["seat#1", "settle#1"]


def test_the_same_geometry_at_eighty_walks_the_whole_chain(chains):
    record = chains[80.0]
    assert record["ok"] is True
    residuals = [s["residual_n"] for s in record["stages"] if "residual_n" in s]
    assert len(residuals) == 3
    assert all(r <= 1e-5 for r in residuals)
    heights = [s["wheel_z_um"] for s in record["stages"] if "wheel_z_um" in s]
    assert heights[0] == pytest.approx(heights[1], abs=1.0)   # the settle does not move z
    assert heights[-1] < heights[1]                            # the second seat does


def test_both_speeds_start_from_the_same_static_state(chains):
    first = [c["stages"][0] for c in chains.values()]
    assert first[0]["residual_n"] == pytest.approx(first[1]["residual_n"], rel=1e-3)
    assert first[0]["wheel_z_um"] == pytest.approx(first[1]["wheel_z_um"], abs=0.1)
