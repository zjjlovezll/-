"""Pin the effective-gap arithmetic: the load split lives on the contact points, not on the crowns.

Round 304 showed that a two-spring split of the **crown** gap puts 5 % fifteen centimetres from where the
solver puts it.  Round 305 seated the whole case at fourteen stations and read the individual bodies'
penetrations, which gives the gap at the two contact points rather than at the two crests.  Every number
pinned here is quoted in ``docs/EFFECTIVE_GAP_2026-11-01.md``.

Three claims are separated on purpose:

* the law is the frozen oracle plus this case's weight, with nothing fitted;
* the crown gap is the wrong abscissa for load: closed with it the error reaches 22.5 percentage points,
  closed with the measured contact depths it stays at 1.3 -- and that closure is an identity, because the
  solver integrates the same law, so it is reported as consistency and not as independent evidence;
* the station where the measured gap reaches the 5 % value lands 0.011 m from the measured 5 % station,
  which is what lets the physical locating gate leave its suspension.

The last item is the one that matters most: the sweep was refined from 0.2 m to 0.05 m **because** the
crossing sat inside one coarse cell.  A test that only pinned the refined number would hide that the coarse
grid could not resolve it, so the coarse answer is recomputed here as well.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import s158_effective_gap as gap  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "effective_gap.json"


@pytest.fixture(scope="module")
def sweep() -> dict:
    if not REPORT.exists():
        pytest.fail(f"the fourteen-station sweep is missing: {REPORT}")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_the_law_is_the_frozen_oracle_and_nothing_else() -> None:
    assert gap.stiffness() == pytest.approx(1.12670e11, rel=1e-4)
    depth = (gap.FROZEN_FORCE_N / gap.stiffness()) ** (2.0 / 3.0)
    assert depth * 1e6 == pytest.approx(65.4661, rel=1e-6)

    # Two equal springs share the load exactly; one spring alone is the whole load; a wider gap unloads
    # the rising body monotonically.
    assert gap.share_of_gap(0.0) == pytest.approx(0.5, abs=1e-12)
    assert gap.share_of_gap(1.0e-3) < 0.01
    shares = [gap.share_of_gap(value) for value in (0.0, 20e-6, 40e-6, 60e-6)]
    assert shares == sorted(shares, reverse=True)
    assert gap.gap_for_share(0.05) * 1e6 == pytest.approx(54.66, abs=0.05)


def test_the_crown_gap_is_the_wrong_abscissa_for_load(sweep: dict) -> None:
    verdict = sweep["verdict"]
    assert verdict["worst_crown_minus_effective_um"] == pytest.approx(31.95, abs=0.05)
    assert verdict["H5_crown_is_effective"] is False
    # Effective gap closes the split; the crown gap leaves 22 points on the floor.
    assert verdict["closure_effective_max_fraction"] <= 0.02
    assert verdict["closure_crown_max_fraction"] >= 0.20
    # The closure with the effective gap is an identity (same law in the solver), so it must be small
    # enough to be useless as evidence -- pinning that keeps anyone from quoting it as a validation.
    assert verdict["closure_effective_max_fraction"] < 0.05


def test_the_effective_gap_places_five_percent_within_a_centimetre(sweep: dict) -> None:
    verdict = sweep["verdict"]
    assert verdict["crossing_count"] == 1
    assert verdict["station_from_effective_m"] == pytest.approx(58.145, abs=0.002)
    assert verdict["station_error_m"] == pytest.approx(0.011, abs=0.002)
    assert verdict["H7_reference_station"] is True
    assert verdict["target_gap_um"] == pytest.approx(54.66, abs=0.05)
    # Two independent routes to the same station: the gap crossing and the share crossing.
    rows = sweep["stations"]
    left = min(rows, key=lambda row: abs(row["station_m"] - 58.125))
    right = min(rows, key=lambda row: abs(row["station_m"] - 58.175))
    assert left["share_measured"] < 0.05 < right["share_measured"]
    share_station = 58.125 + 0.05 * (0.05 - left["share_measured"]) / (
        right["share_measured"] - left["share_measured"]
    )
    assert share_station == pytest.approx(58.154, abs=0.005)


def test_the_crossing_is_interpolated_inside_a_measured_cell(sweep: dict) -> None:
    rows = sweep["stations"]
    station = sweep["verdict"]["station_from_effective_m"]
    left = max(value for value in (row["station_m"] for row in rows) if value <= station)
    right = min(value for value in (row["station_m"] for row in rows) if value >= station)
    assert right - left == pytest.approx(0.05, abs=1e-9)
    assert left < station < right

    # A monotone synthetic series must interpolate inside its own cell ...
    monotone = [
        {"station_m": 10.0, "effective_gap_m": 80e-6},
        {"station_m": 10.2, "effective_gap_m": 40e-6},
        {"station_m": 10.4, "effective_gap_m": 10e-6},
    ]
    assert gap.crossings(monotone, 50e-6) == pytest.approx([10.15])

    # ... and a scrambled one must never be sorted into a station outside its bracketing pair.  Round 305's
    # first version sorted the gaps and reported 57.987 m, which is outside the cell that contains the
    # crossing; this pins the walk instead of the interpolation.
    scrambled = [
        {"station_m": 57.4, "effective_gap_m": 62.8e-6},
        {"station_m": 57.6, "effective_gap_m": 62.8e-6},
        {"station_m": 57.8, "effective_gap_m": 62.8e-6},
        {"station_m": 58.0, "effective_gap_m": 62.84e-6},
        {"station_m": 58.2, "effective_gap_m": 45.39e-6},
        {"station_m": 58.4, "effective_gap_m": 2.36e-6},
        {"station_m": 58.6, "effective_gap_m": -20.23e-6},
        {"station_m": 58.8, "effective_gap_m": 37.22e-6},
    ]
    found = gap.crossings(scrambled, 54.66e-6)
    assert len(found) == 1
    assert found[0] == pytest.approx(58.0938, abs=1e-3)
    assert 58.0 <= found[0] <= 58.2
    assert len(gap.non_monotone_pairs(scrambled)) == 2


def test_the_refinement_is_load_bearing_and_the_tolerance_is_pinned() -> None:
    assert gap.STATION_TOLERANCE_M == pytest.approx(0.10)
    assert np.diff(gap.REFINE_M) == pytest.approx(0.05, abs=1e-12)
    assert np.diff(gap.STATIONS_M) == pytest.approx(0.2, abs=1e-12)
    assert gap.REFINE_M[0] == pytest.approx(58.025, abs=1e-9)
    assert gap.REFINE_M[-1] == pytest.approx(58.175, abs=1e-9)

    # The coarse 0.2 m grid brackets the crossing at 58.094 m -- 0.062 m out, i.e. coarser than the
    # tolerance itself.  That is why the refinement exists, and the test fails if someone deletes it.
    coarse = [
        {"station_m": 57.4 + 0.2 * index, "effective_gap_m": value}
        for index, value in enumerate(
            (62.84e-6, 62.84e-6, 62.80e-6, 62.84e-6, 45.39e-6, 2.36e-6, -20.23e-6, 37.22e-6, 42.74e-6, 26.34e-6)
        )
    ]
    coarse_crossing = gap.crossings(coarse, 54.655758873040426e-6)[0]
    assert coarse_crossing == pytest.approx(58.094, abs=0.002)
    assert abs(coarse_crossing - gap.MEASURED_ENGAGE_5PCT_M) > 0.05
