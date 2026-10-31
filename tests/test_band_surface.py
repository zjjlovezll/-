"""A band surface is two columns only if the columns agree; this pins the disagreement.

Round 271 recovered the same 60 um bump on two passes whose contacts sit 4.6 mm apart.  That gives two
one-dimensional profiles, not a field.  Round 272 joins them and measures the one quantity that decides
whether "z(s, y)" is one object: the difference between the two columns where they overlap.

These tests pin the join's arithmetic, the coverage arithmetic and the pre-registered gates.  They read
the report and do not re-run anything.
"""
from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "band_surface.json"
ABSOLUTE_LIMIT_UM = 22.0


@pytest.fixture(scope="module")
def report() -> dict:
    if not REPORT.exists():
        pytest.skip("band_surface.json not built; run scripts/s129_band_surface.py")
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.mark.corpus
def test_the_two_columns_sit_where_the_seated_sweep_said_they_would(report):
    """The lateral position of each column is measured, not assumed: -7.9 and -3.3 mm from the crown."""
    positions = sorted(column["y_contact_mm"] for column in report["columns"])
    assert positions == pytest.approx([-7.9, -3.3], abs=1e-9)
    deltas = sorted(column["delta_mm"] for column in report["columns"])
    assert deltas == pytest.approx([0.0, 4.0], abs=1e-9)


@pytest.mark.corpus
def test_each_column_clears_the_absolute_gate_on_its_own(report):
    """Two successes are necessary but not sufficient -- this is the per-column half."""
    for column in report["columns"]:
        assert column["p95_um"] <= ABSOLUTE_LIMIT_UM, column
        assert column["amplitude_um"] == pytest.approx(63.3 if column["delta_mm"] == 4.0 else 66.1, abs=0.2)


@pytest.mark.corpus
def test_the_columns_agree_to_a_few_micrometres(report):
    """The join's own gate.  Measured 3.05 um; 5 um is the ceiling this test is willing to defend."""
    consistency = report["consistency"]
    assert consistency["shared_stations"] >= 1200
    assert consistency["p95_um"] <= 5.0
    assert consistency["max_um"] <= 5.0
    assert consistency["p95_um"] <= ABSOLUTE_LIMIT_UM / 4.0


@pytest.mark.corpus
def test_the_observed_region_is_two_bands_and_about_half_the_riding_surface(report):
    """Coverage is reported, never rounded up: 20.6 mm of 37.15 mm, everything else outboard."""
    region = report["observed_region"]
    assert region["head_mm"] == pytest.approx(37.15, abs=0.01)
    assert region["covered_mm"] == pytest.approx(20.6, abs=0.3)
    assert region["coverage"] == pytest.approx(0.554, abs=0.01)
    assert region["span_mm"][0] < -15.0 and region["span_mm"][1] < 5.0
    assert len(region["bands"]) == 2


@pytest.mark.corpus
def test_the_verdict_is_the_one_the_gates_produce(report):
    """No drift between the gates and the sentence: both pass -> single-valued, else not."""
    gates = report["gates"]
    if all(gates[key] for key in ("G-ABS per column", "G-CONSISTENCY")):
        assert "single-valued" in report["verdict"]
    else:
        assert "not single-valued" in report["verdict"]
