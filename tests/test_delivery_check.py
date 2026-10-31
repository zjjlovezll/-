"""The delivered package has to answer for itself on a machine that is not this one.

`scripts/s144_delivery_check.py` reads the three delivered cases, resolves every section reference, hashes the
files, seats the canonical one-set case, integrates the documented 0.02 s and recomputes the delivered summary.
These tests pin the four gates, so a case that starts pointing at `G:\\...` or a section that stops being
bundled fails here instead of at the customer.

Marked `corpus`: it reads the bundled turnout library (~295 files, one seat).
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

pytestmark = pytest.mark.corpus

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports" / "surface_deliverable_2026-10-31" / "delivery_manifest.json"
sys.path.insert(0, str(ROOT / "scripts"))

import s144_delivery_check as check  # noqa: E402


@pytest.fixture(scope="module")
def report() -> dict:
    return check.references()


def test_every_reference_resolves_inside_the_repository(report: dict) -> None:
    gate = check.asset_gate(report)
    assert gate["missing_or_outside"] == 0, gate["missing"]
    assert gate["absolute"] == 0, gate["absolute_examples"]
    assert gate["pass"] is True
    for row in report["references"]:
        assert len(row["sha256"]) == 64, row.get("reference")


def test_the_delivered_set_is_all_three_cases(report: dict) -> None:
    assert set(report["cases"]) == {"one_set", "straight", "diverging"}
    gate = check.asset_gate(report)
    # pinned so that a case silently losing its `bodies`, or the turnout library shrinking, fails loudly
    assert gate["references"] == 1368
    assert gate["unique_files"] == 295


def test_the_canonical_case_still_seats_and_runs_the_documented_twenty_milliseconds() -> None:
    body = check.smoke()
    assert body["pass"] is True
    assert body["frames"] == 41                      # 0.02 s at the 5e-4 s output step
    assert sum(body["gates"].values()) == len(body["gates"]) == 7
    assert body["seat_residual_n"] <= 1.0e-5


def test_the_summary_and_the_manifest_still_agree_with_the_archive() -> None:
    archive = check.summary()
    assert archive["pass"] is True
    assert archive["counts"] == {"PASS": 9, "FAIL": 7, "EXCLUDED": 4, "NOT_RUN": 0}
    if not MANIFEST.exists():
        pytest.skip("the manifest has not been written yet")
    stored = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert stored["assets"]["unique_files"] == 295
    assert stored["smoke"]["frames"] == 41
    # the checkout is self-contained, the wheel is not: exactly one gate may fail, and it is D-WHEEL
    assert stored["assets"]["pass"] and stored["smoke"]["pass"] and stored["summary"]["pass"]
    assert stored["wheel"]["pass"] is False
    assert stored["verdict"] is False


def test_the_wheel_does_not_carry_the_library_yet() -> None:
    """The measured gap this round is about: 104 wheel entries, none of them a section file."""
    wheel = check.wheel_gate()
    if not wheel["built"]:
        pytest.skip("build one first: python -m pip wheel --no-deps -w ../scratch/wheel_m9 .")
    assert wheel["entries"] < 200
    assert wheel["library_entries"] == 0
    assert wheel["section_entries"] == 0
    assert wheel["ships_library"] is False
    assert wheel["pass"] is False
