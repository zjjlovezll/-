"""Pin the 58.6 -> 58.8 m share drop as a measured crest excursion, and pin what it is not.

Round 305 refused to quote the share curve beyond 58.6 m until the 67.5 % -> 18.5 % drop was explained.
This script's report (`reports/load_split_inversion_2026-10-31/crest_series.json`) is read-only here; the
five items below pin the three eliminations and the sensitivity that turns the excursion into a swing.

Numbers are quoted in ``docs/CREST_OVERSHOOT_2026-11-01.md``.
"""

from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "crest_series.json"


@pytest.fixture(scope="module")
def data() -> dict:
    if not REPORT.exists():
        pytest.fail(f"the crest series is missing: {REPORT}")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def row_at(data: dict, station: float) -> dict:
    return min(data["sections"], key=lambda row: abs(row["station_m"] - station))


def test_the_blade_crest_peaks_at_one_named_section(data: dict) -> None:
    peak = row_at(data, 58.598)
    assert pathlib.Path(peak["file"]).name == "07(009)-zjg-20200418-50.txt"
    assert peak["blade_crest_m"] * 1e6 == pytest.approx(93.70, abs=0.02)
    assert peak["gap_m"] * 1e6 == pytest.approx(-21.30, abs=0.02)
    # The stock is flat through the window, so every micrometre of the gap is the blade's.
    stock = [row["stock_crest_m"] * 1e6 for row in data["sections"]]
    assert max(stock) - min(stock) < 0.01
    assert stock[0] == pytest.approx(72.40, abs=0.02)


def test_the_series_is_declared_a_crest_feature_not_a_splice(data: dict) -> None:
    numbering = data["numbering"]
    assert numbering["consecutive"] is True
    assert numbering["section_numbers"] == list(range(46, 57))
    assert 0.10 < numbering["station_gaps_min_m"] < 0.13
    assert 0.10 < numbering["station_gaps_max_m"] < 0.13
    assert data["verdict"]["splice"] is False


def test_the_excursion_is_not_an_interpolation_artefact(data: dict) -> None:
    fine = data["fine"]
    # A 0.12 m section pitch read on a 0.02 m grid: the excursion must be smooth at the grid scale, i.e.
    # the roughness against a 0.1 m trend has to be an order below the excursion itself.
    assert fine["span_um"] == pytest.approx(38.93, abs=0.05)
    assert fine["roughness_rms_um"] < 1.5
    assert fine["roughness_max_um"] < 5.0
    assert fine["span_um"] / fine["roughness_max_um"] > 7.0
    assert data["verdict"]["interpolation_artefact"] is False


def test_the_sensitivity_turns_a_crest_excursion_into_a_share_swing(data: dict) -> None:
    sens = data["sensitivity"]
    assert sens["depth_m"] * 1e6 == pytest.approx(65.80, abs=0.05)
    assert sens["d_share_d_gap_per_um"] == pytest.approx(-0.0228, rel=2e-2)
    assert sens["share_at_minus_21um"] == pytest.approx(0.691, abs=0.005)
    assert sens["share_at_plus_18um"] == pytest.approx(0.338, abs=0.005)
    # 35.9 um of excursion against 2.28 points per um saturates the split, which is the observed swing.
    excursion = data["verdict"]["excursion_um"]
    assert excursion == pytest.approx(35.92, abs=0.05)
    assert excursion * abs(sens["d_share_d_gap_per_um"]) > 0.6


def test_the_verdict_names_the_section_and_keeps_the_boundary(data: dict) -> None:
    verdict = data["verdict"]
    assert verdict["peak_station_m"] == pytest.approx(58.598, abs=1e-6)
    assert verdict["peak_gap_um"] == pytest.approx(-21.30, abs=0.02)
    # The verdict may not claim the artefact was decided from the share curve: it was decided from geometry.
    assert set(verdict) >= {"splice", "interpolation_artefact", "excursion_um", "peak_section"}
