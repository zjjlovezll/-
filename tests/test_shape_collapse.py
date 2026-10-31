"""The onset-collapse probe must answer the same question twice.

Round 257 established that the saturation-onset station carries the amplitude at one bump shape.  The probe
added in round 258 asks whether the offset collapses with `sigma * F(amplitude)`, which only means anything if
the crossing finder, the scaling test and the translation test all behave.  These tests pin those three down on
synthetic input, so a silent change in any of them shows up as a failure rather than as a different verdict.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s121_shape_collapse as probe  # noqa: E402


def test_the_crossing_is_the_first_station_that_reaches_the_threshold() -> None:
    share = np.array([np.nan, 0.10, 0.40, 0.96, 1.00, 1.00])
    assert probe._first_above(share, 0.95) == 3


def test_a_run_that_never_reaches_the_threshold_has_no_crossing() -> None:
    share = np.array([np.nan, 0.10, 0.40, 0.80, 0.94])
    assert probe._first_above(share, 0.95) is None


def test_the_crossing_ignores_leading_nan_frames() -> None:
    share = np.array([np.nan, np.nan, 0.99, 1.0])
    assert probe._first_above(share, 0.95) == 2


def test_proportional_offsets_pass_the_scaling_test() -> None:
    reference = -0.244
    offsets = {0.6: reference * 0.5, 1.2: reference, 2.4: reference * 2.0}
    result = probe.scaling_test(offsets, reference)
    assert result["ok"] is True
    assert result["monotone_in_sigma"] is True


def test_a_non_proportional_offset_fails_the_scaling_test() -> None:
    reference = -0.244
    offsets = {0.6: reference * 0.5, 1.2: reference, 2.4: reference * 1.2}
    result = probe.scaling_test(offsets, reference)
    assert result["ok"] is False


def test_offsets_that_hold_still_pass_the_translation_test() -> None:
    reference = -0.244
    offsets = {57.5: reference, 58.5: reference, 59.5: reference}
    assert probe.translation_test(offsets, reference)["ok"] is True


def test_a_moved_offset_beyond_the_tolerance_fails_the_translation_test() -> None:
    reference = -0.244
    offsets = {57.5: reference + 0.08, 59.5: reference}
    assert probe.translation_test(offsets, reference, tolerance_m=0.05)["ok"] is False


def test_the_route_label_is_what_the_archive_stores() -> None:
    # The lookup matches on this exact string; a rename would quietly find no runs and read as "not measured".
    assert probe.route_of(1.2, 58.5) == "one_set_shape_s1.2_c58.5"
    assert probe.route_of(0.6, 57.5) == "one_set_shape_s0.6_c57.5"


def test_the_probe_uses_the_same_onset_threshold_as_round_257() -> None:
    assert probe.ONSET_SHARE == pytest.approx(0.95)
    assert probe.SMOOTH_M == pytest.approx(0.20)
    assert probe.AMPLITUDE_UM == pytest.approx(100.0)


REPORT = probe.REPORT


@pytest.mark.corpus
def test_amplitude_dominates_shape_which_is_what_the_runs_said() -> None:
    """Round 258's actual finding, pinned so it cannot drift into the hypothesis it replaced.

    The pre-registered collapse (offset proportional to sigma, and translating with the bump centre) failed on
    both axes.  What the four runs show instead is that the onset is anchored to the blade's own lowering ramp:
    at a fixed 100 um amplitude it moves 34 mm when sigma changes 4x, 67 mm when the bump centre moves +-1 m,
    and 144 mm across all four shapes combined, while round 257 moved it 511 mm across 50..200 um.  So amplitude
    dominates shape by 3.5x and the amplitude table transfers across shape and position inside the ramp.
    """
    if not REPORT.exists():
        pytest.skip(f"no report at {REPORT}")
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    onsets = [row["onset_m"] for row in payload["rows"] if row.get("onset_m") is not None]
    if len(onsets) < 4:
        pytest.skip("not every shape run finished")
    spread = max(onsets) - min(onsets)
    assert spread <= 0.20, f"onset spread across sigma and centre is {spread*1e3:.0f} mm, not shape-insensitive"
    amplitude_span = 0.509  # round 257: 58.500 m at 50 um down to 57.989 m at 200 um
    assert amplitude_span / spread >= 3.0, "amplitude must dominate shape by at least 3x"
    assert payload["scaling"]["ok"] is False, "the sigma-proportional collapse was refuted; a pass here means the data changed"
    assert payload["translation"]["ok"] is False, "the centre-translation collapse was refuted; a pass here means the data changed"
    assert "neither axis collapsed" in payload["verdict"]

