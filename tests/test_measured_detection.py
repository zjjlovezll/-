"""Unit tests for the measured-data detector — synthetic, so no .mat file is needed."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import s10_measured_corrugation as detection  # noqa: E402


def _tone(wavelength_m: float, speed_m_s: float, *, rate_hz: float = 4000.0, seconds: float = 0.5) -> np.ndarray:
    time = np.arange(int(rate_hz * seconds)) / rate_hz
    return np.sin(2.0 * np.pi * (speed_m_s / wavelength_m) * time)


def test_auc_is_one_for_separated_sets_and_half_for_identical() -> None:
    inside = np.array([5.0, 6.0, 7.0])
    outside = np.array([1.0, 2.0, 3.0])
    assert detection.auc(inside, outside) == 1.0
    assert abs(detection.auc(inside, inside.copy()) - 0.5) < 1e-12


def test_auc_counts_ties_as_half() -> None:
    assert abs(detection.auc(np.array([2.0]), np.array([2.0])) - 0.5) < 1e-12


def test_band_follows_speed_not_the_calendar() -> None:
    """A 26 mm wave is 800 Hz at 75 km/h and 445 Hz at 40 km/h; the band must say so."""
    fast = detection.band_for_speed(75.0 / 3.6, 4000.0)
    slow = detection.band_for_speed(40.0 / 3.6, 4000.0)
    assert abs(fast[0] - (75.0 / 3.6) / 0.040) < 1e-9
    assert abs(fast[1] - (75.0 / 3.6) / 0.018) < 1e-9
    assert slow[0] < fast[0] and slow[1] < fast[1]
    # and the wavelength is the same in both, which is the whole point
    assert abs((75.0 / 3.6) / np.mean(fast) - (40.0 / 3.6) / np.mean(slow)) < 2e-3


def test_prominence_sees_a_tone_inside_the_band_and_ignores_one_outside() -> None:
    speed = 62.0 / 3.6
    inside = _tone(0.026, speed)
    outside = _tone(0.400, speed)  # 400 mm is well below the 18-40 mm band
    inside_db, inside_hz = detection.prominence(inside, 4000.0, speed)
    outside_db, _ = detection.prominence(outside, 4000.0, speed)
    assert inside_db > 20.0, inside_db
    assert abs(inside_hz - speed / 0.026) < 30.0, inside_hz
    assert outside_db < inside_db - 10.0


def test_prominence_is_zero_when_the_segment_is_too_short() -> None:
    ratio, peak = detection.prominence(np.zeros(10), 4000.0, 17.0)
    assert ratio == 0.0 and peak == 0.0


def test_score_flags_a_section_only_when_its_peak_clears_the_threshold() -> None:
    windows = []
    # the whole recorded span, so every section has windows of its own
    for index, position in enumerate(np.arange(3.800e3, 6.300e3, 5.0)):
        position = float(position)
        # loud inside every section, quiet between -- the AUC compares the union of the
        # sections against everything else, so a single loud section would drag it down
        loud = any(start <= position <= stop for _name, start, stop in detection.SECTIONS)
        windows.append(
            detection.Window(
                position_m=position,
                speed_m_s=17.0,
                index_db=30.0 if loud else 10.0 + 0.01 * (index % 5),
                peak_hz=760.0,
                rms=1.0,
            )
        )
    summary = detection.score(windows, "synthetic")
    rows = {row["section"]: row for row in summary["rows"]}
    assert summary["sections_detected"] == len(detection.SECTIONS)
    assert all(
        row["localisation_error_m"] == 0.0
        for row in rows.values()
        if row["inside_max_db"] is not None
    )
    assert summary["pseudo_sections"] > 10, "the threshold must come from pseudo-sections"
    assert summary["auc"] > 0.9


def test_a_peak_just_past_a_section_end_is_found_with_a_non_zero_error() -> None:
    """The old error was measured from a peak the mask had already constrained, so it could
    only ever print 0 m.  Here five sections are loud inside and S6 is quiet inside but has a
    bump 10 m past its end, which the calibrated threshold must still admit.

    The calibration region has to stay quiet: six loud bumps sitting outside the sections
    would raise the 95th percentile above them, which is the false-alarm control doing its
    job rather than a bug.
    """
    sections = detection.SECTIONS
    loud_sections = sections[:-1]
    late_name, late_start, late_stop = sections[-1]
    extra = (late_stop + 8.0, late_stop + 18.0)
    windows = []
    for index, position in enumerate(np.arange(3.800e3, 6.300e3, 5.0)):
        position = float(position)
        loud = any(start <= position <= stop for _name, start, stop in loud_sections)
        late = extra[0] <= position <= extra[1]
        windows.append(
            detection.Window(
                position_m=position,
                speed_m_s=17.0,
                index_db=30.0 if (loud or late) else 10.0 + 0.01 * (index % 5),
                peak_hz=760.0,
                rms=1.0,
            )
        )
    summary = detection.score(windows, "one late peak")
    rows = {row["section"]: row for row in summary["rows"]}
    assert rows[late_name]["detected"], "the bump 10 m past the end is within the search radius"
    assert rows[late_name]["localisation_error_m"] > 8.0
    assert rows[late_name]["localisation_error_m"] <= detection.SEARCH_M + 1e-9
    for name, _start, _stop in loud_sections:
        assert rows[name]["detected"]
        assert rows[name]["localisation_error_m"] == 0.0

def test_an_empty_record_detects_nothing_at_the_calibrated_rate() -> None:
    """With no loud section the calibrated threshold must leave (almost) no hits, which is
    what the window-level threshold could not promise."""
    windows = []
    for index, position in enumerate(np.arange(3.800e3, 6.300e3, 5.0)):
        windows.append(
            detection.Window(
                position_m=float(position),
                speed_m_s=17.0,
                index_db=10.0 + 0.01 * (index % 5),
                peak_hz=760.0,
                rms=1.0,
            )
        )
    summary = detection.score(windows, "empty")
    assert summary["sections_detected"] == 0
    assert summary["null_probability"] > 0.5
