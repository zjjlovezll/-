"""Tests for the M7 assembly: one light band reconstructed end to end and judged.

The two bugs worth pinning are the ones this round actually hit: an inversion that came out monotone
the wrong way (higher blade share mapped to a wider gap), and a scorer that was fed a truth in metres
while the reconstruction was in micrometres.  Both are arithmetic, both are cheap to check here.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s123_m7_assembly as assembly  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "m7_assembly.json"


def test_the_law_anchor_is_the_one_round_256_measured():
    _, _, anchor = assembly.build_law()
    assert anchor["width_mm"] == pytest.approx(45.19, abs=0.05)
    assert anchor["station_m"] == pytest.approx(58.0, abs=0.05)
    assert anchor["half_gap_um"] == pytest.approx(56.15, abs=0.30)


def test_the_half_load_gap_is_the_fixed_point_of_the_law():
    """By construction sigma = 0.5 sits at u = g0(w); that is what makes the width curve usable."""
    half_gap_of, invert, _ = assembly.build_law()
    for width in (45.0, 63.0, 72.0):
        gap = half_gap_of(width)
        assert invert(0.5, gap) == pytest.approx(gap, abs=0.5)


def test_the_inversion_is_monotone_and_does_not_collapse_onto_a_clamp():
    half_gap_of, invert, _ = assembly.build_law()
    gap = half_gap_of(45.19)
    values = [invert(sigma, gap) for sigma in (0.1, 0.3, 0.5, 0.7, 0.9)]
    assert all(abs(b - a) > 1.0 for a, b in zip(values, values[1:])), values
    assert (values[-1] - values[0]) > 20.0


def test_a_wider_section_sits_at_a_different_half_load_gap():
    half_gap_of, _, _ = assembly.build_law()
    narrow, wide = half_gap_of(45.0), half_gap_of(72.0)
    assert narrow > 20.0 and abs(wide) < 5.0
    assert narrow - wide == pytest.approx(57.7, abs=5.0)


def test_the_scorer_is_exact_when_the_reconstruction_is_the_truth():
    stations = np.linspace(55.0, 62.0, 400)
    truth = assembly.base._true_bump(stations, 100.0)
    hit = {"route": "synthetic", "run_id": "synthetic", "stations": stations, "z": truth.copy(),
           "share": np.zeros_like(stations), "valid": np.ones_like(stations, bool)}
    row = assembly.score(hit, 100.0, None)
    assert row["p95_um"] == pytest.approx(0.0, abs=1e-9)
    assert row["worst_bin_relative_pct"] == pytest.approx(0.0, abs=1e-9)
    assert row["peak_error_m"] == pytest.approx(0.0, abs=1e-9)
    assert all(row["gates"].values())


@pytest.mark.corpus
def test_the_assembly_report_pins_the_failure_it_found():
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    assert payload["null_ok"] is False
    assert payload["amplitudes_passing_all_gates"] == 0
    assert payload["null"]["p95_um"] == pytest.approx(43.0, abs=3.0)

    rows = payload["amplitudes"]
    assert [row["truth_peak_um"] for row in rows] == [50.0, 100.0, 200.0]
    assert rows[0]["p95_um"] == pytest.approx(98.1, abs=5.0)
    # the estimate is not monotone in the amplitude: that is the finding, not a rounding wobble
    estimated = [row["estimated_peak_um"] for row in rows]
    assert estimated[1] > estimated[0] and estimated[2] < estimated[1]
    # localisation survives where the profile does not
    assert rows[2]["gates"]["G-LOC"] is True
    assert payload["coverage"]["identifiable_mm"] / payload["coverage"]["head_mm"] < 0.15
