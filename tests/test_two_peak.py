"""Two peaks, not one: the forward fit has to find a profile, and the gates judge each peak.

Round 261 fitted one bump; M8 needs a corrugated surface, so this asks the cheapest version of that
question -- a profile with two gaussians whose number is declared and whose positions and amplitudes
are not.  The peaks sit 1.8 m apart at a 0.35 m width, so a merge would be the fit's failure and not a
resolution limit.

These tests pin the construction and the report's arithmetic; they do not re-run the simulation.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VARIANT = ROOT.parent / "scratch" / "s130" / "one_set_twopeak.json"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "two_peak_fit.json"
PEAKS = ((57.6, 50.0), (59.4, 30.0))
WIDTH_M = 0.35
ABSOLUTE_LIMIT_UM = 22.0


@pytest.fixture(scope="module")
def variant() -> dict:
    if not VARIANT.exists():
        pytest.skip("one_set_twopeak.json not built; run scripts/s130_two_peak.py --build")
    return json.loads(VARIANT.read_text(encoding="utf-8"))


@pytest.mark.corpus
def test_the_built_profile_has_two_peaks_where_they_were_declared(variant):
    """The case must carry the declared profile, otherwise the report would be graded against a guess."""
    blade = [body for body in variant["rail_templates"][1]["bodies"] if body["id"] == "blade"][0]
    stations = np.asarray([float(st["s_m"]) for st in blade["stations"]])
    heights = np.asarray([float(st["profile"].get("z_offset_m", 0.0)) for st in blade["stations"]]) * 1e6

    for centre, amplitude in PEAKS:
        nearest = int(np.argmin(np.abs(stations - centre)))
        assert heights[nearest] == pytest.approx(amplitude, abs=1.0), (centre, heights[nearest])
        # the other peak must not be responsible for this height: it is >4 widths away
        other = sum(a * np.exp(-0.5 * ((stations[nearest] - c) / WIDTH_M) ** 2)
                    for c, a in PEAKS if abs(c - centre) > 1e-9)
        assert other < 0.05 * amplitude

    # and the valley between the two peaks is deep, so "two peaks" is not a label on one bump.
    # Measured valley bottom 3.03 um at 58.6 m, against the smaller peak's 30 um: 20 % is the ceiling.
    between = (stations > PEAKS[0][0] + 0.3) & (stations < PEAKS[1][0] - 0.3)
    valley = float(heights[between].min())
    assert valley < 0.20 * min(amplitude for _, amplitude in PEAKS), valley
    assert valley < float(heights[between].max()) / 3.0


@pytest.mark.corpus
def test_the_report_judges_each_peak_separately():
    """G-LOC and G-AMP are per peak by construction; a merged fit cannot pass them silently."""
    if not REPORT.exists():
        pytest.skip("two_peak_fit.json not built; run scripts/s130_two_peak.py --report")
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    assert len(payload["per_peak"]) == 2
    for row in payload["per_peak"]:
        assert set(row) >= {"centre_true_m", "centre_fit_m", "location_error_m",
                            "amplitude_true_um", "amplitude_fit_um", "amplitude_relative_pct"}
        assert row["location_error_m"] == pytest.approx(
            abs(row["centre_fit_m"] - row["centre_true_m"]), abs=1e-12)
    assert {round(row["amplitude_true_um"], 1) for row in payload["per_peak"]} == {50.0, 30.0}


@pytest.mark.corpus
def test_the_gates_are_the_round_261_ones_plus_separation():
    """Four gates, three of them inherited unchanged; separation is new and declared with the build."""
    if not REPORT.exists():
        pytest.skip("report not built")
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    assert set(payload["gates"]) == {"G-ABS", "G-LOC", "G-AMP", "G-SEP"}
    assert payload["separation_m"] >= 0.0
    if payload["gates"]["G-SEP"]:
        assert payload["separation_m"] >= 0.5
    if payload["gates"]["G-ABS"]:
        assert payload["p95_um"] <= ABSOLUTE_LIMIT_UM
    # the verdict must follow the gates rather than the other way round
    all_pass = all(payload["gates"].values())
    assert ("both peaks are recovered" in payload["verdict"]) == all_pass


@pytest.mark.corpus
def test_the_width_prior_is_declared_and_narrower_than_the_single_bump_of_round_261():
    """A narrower prior is what makes two peaks separable; it is stated, not inferred."""
    if not REPORT.exists():
        pytest.skip("report not built")
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    assert payload["width_m_prior"] == pytest.approx(WIDTH_M)
    assert payload["width_m_prior"] < 1.2      # round 261's single-bump width
    assert payload["peaks_true"] == [list(peak) for peak in PEAKS] or payload["peaks_true"] == [list(p) for p in PEAKS]
