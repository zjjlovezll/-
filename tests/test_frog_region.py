"""The frog is in the case, and it can never carry the wheel.

Round 317 asked why no archive ever reached the frog (103.280-116.440 m) and ran a short window to
read the wing-rail-to-point-rail transfer.  Two things came out, both geometric and both cheap to
pin: the frog body carries the designed lowering (13.96 mm at the nose, falling to zero by 104.42 m),
but the stock rail body runs *through* the crossing at +0.072 mm, so the frog's crown tops out
0.072 mm below the running surface and never touches the wheel.  Three bodies within 0.072 mm at the
same lateral position is also why a z-only seat cannot converge there (gtol at 103 m, xtol at 100 m).

These assertions run in a second and need no simulation.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from velch.vehicle import load_vehicle_case

CASE = Path(__file__).resolve().parents[1] / "vehicles/turnouts/CN60-1100-1_18/cases/straight_one_set.json"
NOSE_M = 103.28
FLUSH_M = 104.42


def _right_bodies():
    case = load_vehicle_case(CASE)
    rail = [rail for rail in case.rails if rail.axle_index == 0][1]
    return rail, {str(body.id).split(":")[-1]: body for body in rail.bodies}


def _crown_mm(body, station_m: float) -> float | None:
    try:
        sample = body.series.sample(station_m, 1.0)
    except Exception:
        return None
    return float(np.nanmax(np.asarray(sample.profile.z_m, dtype=float))) * 1e3


def test_the_case_carries_three_bodies_on_the_right_rail() -> None:
    rail, bodies = _right_bodies()
    assert rail.id == "axle1_right"
    assert set(bodies) == {"stock", "blade", "frog"}


def test_the_frog_nose_sits_13_96_mm_below_the_running_surface() -> None:
    _, bodies = _right_bodies()
    nose = _crown_mm(bodies["frog"], NOSE_M)
    assert nose is not None and nose == pytest.approx(-13.962, abs=0.01)


def test_the_frog_reaches_its_full_height_by_104_42_m() -> None:
    _, bodies = _right_bodies()
    flush = _crown_mm(bodies["frog"], FLUSH_M)
    assert flush is not None and abs(flush) < 0.05


def test_the_stock_rail_runs_through_the_crossing() -> None:
    """If this ever fails, the crossing was rebuilt and the transfer becomes measurable."""

    _, bodies = _right_bodies()
    crowns = [_crown_mm(bodies["stock"], station) for station in (90.0, 103.28, 110.0, 116.0)]
    assert all(crown is not None for crown in crowns)
    assert crowns == pytest.approx([0.072] * 4, abs=5e-4)


def test_the_frog_never_reaches_the_running_surface() -> None:
    """The measured reason no transfer can happen: the frog tops out below the stock rail."""

    _, bodies = _right_bodies()
    worst = None
    for station in np.arange(103.28, 116.44, 0.5):
        frog = _crown_mm(bodies["frog"], float(station))
        stock = _crown_mm(bodies["stock"], float(station))
        if frog is None or stock is None:
            continue
        gap = stock - frog
        worst = gap if worst is None else max(worst, gap)
    assert worst is not None and worst >= 0.0, f"the frog overtops the stock rail by {-worst:.4f} mm"
