"""The archived run still matches the reference (needs the corpus, hence the marker)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "src"
REFERENCE = REPO / "docs" / "physics_invariants.json"

sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(REPO / "scripts"))

pytestmark = pytest.mark.corpus


def _module():
    spec = importlib.util.spec_from_file_location(
        "physics_invariants", REPO / "scripts" / "physics_invariants.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_the_archive_still_matches_the_reference() -> None:
    module = _module()
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    observed = module.from_archive()
    assert module.compare(reference, observed) == []
    assert observed["overall_peak_contact"] == "axle2_right_normal_n"
    assert len(observed["contact_peaks_kn"]) == 8


def test_a_moved_number_is_reported_not_ignored() -> None:
    module = _module()
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    observed = module.from_archive()
    moved = json.loads(json.dumps(reference))
    moved["contact_peaks_kn"]["axle2_right_normal_n"] += 5.0
    problems = module.compare(moved, observed)
    assert any("axle2_right_normal_n" in problem for problem in problems)


def test_the_reference_quotes_the_numbers_the_documents_do() -> None:
    """9.13 kN / 57.14 Hz are cited in the S2 doc; a reference that disagrees protects nothing."""

    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    window = reference["window_metrics"]
    assert window["rms_kn"] == pytest.approx(9.13, abs=0.05)
    assert window["dominant_hz"] == pytest.approx(57.14, abs=0.1)
    assert reference["lead_axle_right_peak_kn"] == pytest.approx(89.68, abs=0.02)
    assert reference["overall_peak_kn"] == pytest.approx(170.61, abs=0.02)
