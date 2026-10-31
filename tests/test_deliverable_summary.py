"""The deliverable summary cannot drift from the archived reports.

Every claim in `docs/DELIVERABLE_SUMMARY_2026-10-31.md` is read from a stored report by
`scripts/s143_deliverable_summary.py`.  These tests recompute the summary and compare it with the copy on disk,
so a report that changes underneath fails here instead of relabelling the headline quietly.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "load_split_inversion_2026-10-31"
SUMMARY = ROOT / "reports" / "surface_deliverable_2026-10-31" / "deliverable_summary.json"
sys.path.insert(0, str(ROOT / "scripts"))

import s143_deliverable_summary as summary_script  # noqa: E402


@pytest.fixture(scope="module")
def stored() -> dict:
    if not SUMMARY.exists():
        pytest.skip("the deliverable summary has not been produced yet")
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_the_status_vocabulary_is_closed(stored: dict) -> None:
    statuses = {item["status"] for item in stored["items"]}
    assert statuses <= {"PASS", "FAIL", "EXCLUDED", "NOT_RUN"}
    assert stored["counts"] == {"PASS": 9, "FAIL": 7, "EXCLUDED": 4, "NOT_RUN": 0}


def test_every_item_is_backed_by_its_own_report(stored: dict) -> None:
    for item in stored["items"]:
        assert item["status"] != "NOT_RUN", item["report"]
        # PASS needs the claim to hold; EXCLUDED needs the mechanism to provably miss; FAIL is the one case
        # where the report is expected to contradict the claim
        expected_support = item["status"] in ("PASS", "EXCLUDED")
        assert item["supported"] is expected_support, (
            item["report"], item["status"], item["supported"])


def test_the_summary_is_recomputable_from_the_reports(stored: dict) -> None:
    assert summary_script.coverage() == stored["coverage"]
    assert summary_script.surface() == stored["band_surface"]
    for name, label, status, support in summary_script.ITEMS:
        report = json.loads((REPORTS / name).read_text(encoding="utf-8"))
        assert bool(support(report)) == (status in ("PASS", "EXCLUDED")), name


def test_the_coverage_arithmetic_is_the_stored_one(stored: dict) -> None:
    source = json.loads((REPORTS / "lateral_coverage.json").read_text(encoding="utf-8"))
    assert stored["coverage"]["head_mm_5mm"] == pytest.approx(source["coverage"]["head_width_mm"], abs=1e-6)
    assert stored["coverage"]["covered_share_5mm"] == pytest.approx(source["coverage"]["coverage"], abs=1e-12)
    assert stored["coverage"]["gauge_settings_that_seat"] == source["passes_ok"]
    # the uncovered part cannot be reached by gauge alone: +14 mm more bed, i.e. a non-turnout geometry
    assert stored["coverage"]["covered_share_5mm"] < 0.60


def test_the_band_surface_matches_its_report(stored: dict) -> None:
    source = json.loads((REPORTS / "band_surface.json").read_text(encoding="utf-8"))
    assert stored["band_surface"]["p95_consistency_um"] == pytest.approx(source["consistency"]["p95_um"])
    assert stored["band_surface"]["columns"] == len(source["observed_region"]["bands"])
    assert stored["band_surface"]["coverage"] == pytest.approx(source["observed_region"]["coverage"])


def test_the_unachieved_list_is_present_and_specific(stored: dict) -> None:
    text = " ".join(stored["not_achieved"])
    assert "random" in text
    assert "coverage" in text
    assert "truth" in text
    assert len(stored["not_achieved"]) == 3
