"""The split law resolved by section width: what it fixes, and where the observable saturates.

Round 255 measured that the half-load gap moves with the blade's section width.  s119 puts that into the
inversion and re-runs the three hold-out amplitudes with **no fitting to the bump runs at all**: the law
comes from the s118 static probes, the geometry from the canonical case, the widths from the station file
names, the split from the archived runs.

The result is deliberately split in two, because the two halves say different things:
  * the 50 um fold improves (1.37 % -> 0.53 % relative), so width-awareness does correct the small end;
  * 100 and 200 um collapse to the same ~62 um estimate, because sigma saturates once the gap closes past
    about -50 um and the inversion is clamped at the end of the measured curve.
"""
from __future__ import annotations

import json
import math
import pathlib

import pytest

REPORT = pathlib.Path(__file__).resolve().parents[1] / "reports" / "load_split_inversion_2026-10-31"
WIDTH_REPORT = pathlib.Path(__file__).resolve().parents[2] / "scratch" / "s119" / "inversion_width_aware.json"

pytestmark = pytest.mark.corpus


@pytest.fixture(scope="module")
def payload() -> dict:
    if not WIDTH_REPORT.exists():
        pytest.skip(f"{WIDTH_REPORT} is missing; run scripts/s119_width_aware_inversion.py first")
    return json.loads(WIDTH_REPORT.read_text(encoding="utf-8"))


def test_the_anchors_move_with_the_section_width(payload: dict) -> None:
    anchors = {round(float(a["width_mm"]), 1): float(a["half_gap_um"]) for a in payload["anchors"]}
    # The two narrowest stations never reach sigma = 0.5 inside the grid (their blade sits millimetres
    # down, so the probe would have to unload the stock entirely); they are reported as nan, not dropped.
    unmeasured = [width for width, value in anchors.items() if not math.isfinite(value)]
    measured = {width: value for width, value in anchors.items() if math.isfinite(value)}
    assert unmeasured, anchors
    # A narrow section needs real closure before the blade wins half the load; a wide one needs none.
    # A width-blind law cannot express that difference, and that is the point.
    narrow = min(value for width, value in measured.items() if width < 50.0)
    wide = max(abs(value) for width, value in measured.items() if width >= 60.0)
    assert narrow > 50.0, measured
    assert wide < 5.0, measured


def test_the_small_amplitude_fold_now_recovers_the_peak(payload: dict) -> None:
    row = next(r for r in payload["rows"] if float(r["amplitude_um"]) == 50.0)
    assert row["gate_a"] is True, row
    assert row["relative_pct"] <= 2.0, row
    # the station gate is not met in this family; assert the number rather than the verdict
    assert row["station_error_m"] <= 0.7, row


def test_the_split_saturates_so_the_two_large_amplitudes_are_indistinguishable(payload: dict) -> None:
    rows = {float(r["amplitude_um"]): r for r in payload["rows"]}
    assert payload["folds_passing_all_three"] == 0
    small = rows[100.0]["peak_um"]
    large = rows[200.0]["peak_um"]
    # a 2x step in the truth moves the estimate by less than 20 %, so amplitude is not carried by sigma
    assert abs(large - small) / small < 0.20, (small, large)
    assert rows[200.0]["relative_pct"] > 10.0


def test_the_saturation_onset_station_moves_with_the_amplitude(payload: dict) -> None:
    stations = [float(r["peak_station_m"]) for r in
                sorted(payload["rows"], key=lambda r: float(r["amplitude_um"]))]
    # larger bump -> saturation starts earlier -> the peak reported from the clamped end moves upstream
    assert stations[0] > stations[1] > stations[2], stations
    steps = [stations[i] - stations[i + 1] for i in range(2)]
    assert all(0.05 <= step <= 0.60 for step in steps), steps
