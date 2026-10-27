"""The validation status is a claim, so a simulation alone must never make one."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from velch.inverse import verdict as verdict_module
from velch.inverse.verdict import FAILED, PASSED, LayerResult, Verdict

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "src" / "velch"


def _verdict(status: str, *, detected: bool | None = None,
             consistent: bool | None = None) -> Verdict:
    metrics = {"criterion": "recorded sections"}
    if detected is not None:
        metrics["detected"] = detected
    if consistent is not None:
        metrics["consistent_with_recorded_section"] = consistent
    notes = "" if status != FAILED else "recorded sections not all reproduced"
    return Verdict(
        record="Run_75kmh_E1toE2.mat",
        layers=[LayerResult("L5_acceptance", status, metrics=metrics, notes=notes)],
    )


def test_the_manifest_default_makes_no_claim(tmp_path):
    """A run on its own cannot say its numbers were validated against a measurement."""
    import shutil

    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

    # Copy the whole example directory: the case refers to its profiles by relative name, and a bare
    # case.json in a temp folder cannot resolve them (AssetRefError, learned the hard way).
    bundle = tmp_path / "vehicle_v2"
    shutil.copytree(REPO / "examples" / "vehicle_v2", bundle)
    case_path = bundle / "case.json"
    raw = json.loads(case_path.read_text(encoding="utf-8"))

    def _absolutise(node):
        """The asset resolver needs a resolvable path; a copied case loses its relative root."""
        if isinstance(node, dict):
            return {key: _absolutise(value) for key, value in node.items()}
        if isinstance(node, list):
            return [_absolutise(value) for value in node]
        if isinstance(node, str) and node.endswith((".csv", ".txt", ".prr")):
            candidate = bundle / node
            if candidate.exists():
                return str(candidate)
        return node

    raw = _absolutise(raw)
    raw["run"].update({"duration_s": 0.005, "output_step_s": 0.005})
    raw.pop("initial_state", None)
    path = tmp_path / "case.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")

    loaded = load_vehicle_case(path)
    result = simulate_vehicle(loaded)
    _, manifest_path = save_vehicle_result(loaded, result, tmp_path / "out")
    summary = json.loads(Path(manifest_path).read_text(encoding="utf-8"))["summary"]
    assert summary["measurement_validation_status"] == "not_evaluated"
    assert summary["physics_validation_status"] == "unvalidated_against_measurement_or_Simpack"


def test_only_the_acceptance_layer_may_claim_more():
    """Source scan: no module outside velch/inverse/verdict.py may produce these values."""
    allowed = SOURCE / "inverse" / "verdict.py"
    owning = set(verdict_module.STATUS_MEANINGS)
    offenders = []
    for path in SOURCE.rglob("*.py"):
        if path == allowed:
            continue
        text = path.read_text(encoding="utf-8")
        for status in owning:
            if f'"{status}"' in text and status != "not_evaluated":
                offenders.append((path.relative_to(SOURCE), status))
    assert offenders == []


def test_a_failed_acceptance_licenses_only_detection():
    assert _verdict(FAILED, detected=True).measurement_validation_status == "detection_only"
    assert _verdict(FAILED, detected=False).measurement_validation_status == "not_evaluated"
    assert _verdict(FAILED).measurement_validation_status == "not_evaluated"


def test_a_passed_acceptance_licenses_the_section_claim_only_with_evidence():
    assert _verdict(PASSED, consistent=True).measurement_validation_status == (
        "consistent_with_recorded_section"
    )
    assert _verdict(PASSED).measurement_validation_status == "not_evaluated"


def test_every_status_has_a_meaning():
    assert set(verdict_module.MEASUREMENT_STATUSES) == set(verdict_module.STATUS_MEANINGS)
    assert "not_evaluated" in verdict_module.STATUS_MEANINGS
    assert all(verdict_module.STATUS_MEANINGS.values())
