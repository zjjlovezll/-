"""The saturation-onset station: the one observable that still moves above the split's knee.

Round 256 showed the split saturates: 100 um and 200 um bumps both read about 62 um of gap closure.  What still
moves is *where* saturation starts.  These tests pin the three things that make that usable as an observable:

  * the onset is the first station at which the smoothed share reaches 0.95, not the argmax (the split sits on a
    plateau, so the argmax wanders inside it);
  * for the amplitudes already archived the onset is monotone in amplitude and steps by more than one output
    frame, so the station is not a plateau in disguise;
  * a campaign that does collapse onto one station is reported as collapsed rather than as a pass.

The campaign that extends this to 20-120 um is a separate run set; when those runs are present the same
assertions cover them, and when they are not the test still pins the three archived amplitudes.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import s120_onset_resolution as onset  # noqa: E402

pytestmark = pytest.mark.corpus

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "onset_resolution.json"


def test_the_onset_is_the_first_crossing_and_missing_values_are_ignored():
    share = np.array([np.nan, 0.10, 0.96, 0.99, 0.20])
    assert onset._first_above(share, 0.95) == 2
    # a nan above the threshold must not be mistaken for a crossing
    assert onset._first_above(np.array([np.nan, np.nan]), 0.95) is None
    assert onset._first_above(np.array([0.10, 0.20]), 0.95) is None


def test_a_plateau_is_called_collapsed_and_is_not_a_pass():
    monotone, resolvable, collapsed, verdict = onset._verdict([0.0, -1e-9], onset.GRID_M)
    assert collapsed is True
    assert not (monotone and resolvable and not collapsed)
    assert "does NOT" in verdict


def test_a_sub_grid_step_is_reported_as_unresolvable():
    half = -0.5 * onset.GRID_M
    monotone, resolvable, collapsed, verdict = onset._verdict([half], onset.GRID_M)
    assert monotone is True
    assert resolvable is False
    assert "does NOT" in verdict


def test_the_archived_amplitudes_move_the_onset_by_more_than_one_frame():
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    rows = [row for row in payload["rows"] if row["status"] == "ok"]
    assert len(rows) >= 3, payload["rows"]
    rows.sort(key=lambda row: row["amplitude_um"])
    onsets = [row["onset_station_m"] for row in rows]
    # larger bump saturates earlier
    assert all(later < earlier for earlier, later in zip(onsets, onsets[1:])), onsets
    steps = [earlier - later for earlier, later in zip(onsets, onsets[1:])]
    assert min(steps) > payload["grid_m"], steps
    # and the definition really is the crossing on the rising flank, not a free-floating argmax: the two have
    # to sit within a tenth of a metre of each other (at 50 um they even swap order by one frame).
    assert all(abs(row["onset_station_m"] - row["peak_station_m"]) <= 0.10 for row in rows), rows
