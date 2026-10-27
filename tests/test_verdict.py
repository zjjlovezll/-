"""Tests for the verdict: the derived status rule, the refusals, and the tables."""

from __future__ import annotations

import json

import pytest

from velch.inverse.verdict import (
    FAILED,
    MEASUREMENT_STATUSES,
    PASSED,
    SKIPPED,
    LayerResult,
    Verdict,
    VerdictError,
    write_table,
)


def _layer(name: str, status: str = PASSED, **metrics) -> LayerResult:
    payload = metrics or {"value": 1.0}
    return LayerResult(name=name, status=status, metrics=payload)


def test_status_is_not_evaluated_without_an_acceptance_layer():
    verdict = Verdict(record="r.mat")
    verdict.add(_layer("L0_admission"))
    assert verdict.measurement_validation_status == "not_evaluated"


def test_detection_only_when_acceptance_failed_but_detected():
    verdict = Verdict(record="r.mat")
    verdict.add(LayerResult(name="L5_acceptance", status=FAILED, metrics={"detected": 3, "sections": 6},
                            notes="3 of 6 sections detected; the pre-registered bar was 6 of 6"))
    assert verdict.measurement_validation_status == "detection_only"


def test_not_evaluated_when_acceptance_failed_without_detection():
    verdict = Verdict(record="r.mat")
    verdict.add(LayerResult(name="L5_acceptance", status=FAILED, metrics={"detected": 0},
                            notes="nothing detected"))
    assert verdict.measurement_validation_status == "not_evaluated"


def test_consistent_only_when_acceptance_passed_with_the_flag():
    passing = Verdict(record="r.mat")
    passing.add(_layer("L5_acceptance", consistent_with_recorded_section=True))
    assert passing.measurement_validation_status == "consistent_with_recorded_section"

    passing_without_flag = Verdict(record="r.mat")
    passing_without_flag.add(_layer("L5_acceptance"))
    assert passing_without_flag.measurement_validation_status == "not_evaluated"


def test_every_status_carries_a_meaning():
    for status in MEASUREMENT_STATUSES:
        verdict_modes = [
            Verdict(record="x").measurement_validation_status,
        ]
        assert verdict_modes[0] in MEASUREMENT_STATUSES
        from velch.inverse.verdict import STATUS_MEANINGS

        assert STATUS_MEANINGS[status]


def test_refusals_name_the_problem():
    with pytest.raises(VerdictError) as unknown_layer:
        LayerResult(name="L9_magic", status=PASSED, metrics={"value": 1.0})
    assert "unknown layer" in str(unknown_layer.value)

    with pytest.raises(VerdictError) as unknown_status:
        LayerResult(name="L0_admission", status="maybe", metrics={"value": 1.0})
    assert "unknown status" in str(unknown_status.value)

    with pytest.raises(VerdictError) as silent_failure:
        LayerResult(name="L0_admission", status=FAILED, metrics={"value": 1.0})
    assert "without saying why" in str(silent_failure.value)

    with pytest.raises(VerdictError) as empty_pass:
        LayerResult(name="L0_admission", status=PASSED, metrics={})
    assert "no metrics" in str(empty_pass.value)

    verdict = Verdict(record="r.mat")
    verdict.add(_layer("L0_admission"))
    with pytest.raises(VerdictError) as duplicate:
        verdict.add(_layer("L0_admission"))
    assert "twice" in str(duplicate.value)


def test_layers_are_kept_in_the_documented_order():
    verdict = Verdict(record="r.mat")
    verdict.add(_layer("L3_inversion"))
    verdict.add(_layer("L0_admission"))
    verdict.add(LayerResult(name="L2_calibration", status=SKIPPED, notes="single speed only"))
    assert [result.name for result in verdict.layers] == ["L0_admission", "L2_calibration", "L3_inversion"]


def test_the_verdict_serialises_and_writes(tmp_path):
    verdict = Verdict(record="r.mat", version="0.4.36")
    verdict.add(_layer("L0_admission", samples=579740))
    verdict.add(LayerResult(name="L5_acceptance", status=FAILED, metrics={"detected": 3},
                            notes="3 of 6", evidence=["reports/auto_accept.json"]))
    verdict.degradation.append("amplitude claims withdrawn: single speed, no second-speed control")

    target = verdict.write(tmp_path / "verdict.json")
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert payload["measurement_validation_status"] == "detection_only"
    assert payload["physics_validation_status"] == "unvalidated_against_measurement_or_Simpack"
    assert payload["degradation"]
    assert payload["layers"][0]["metrics"]["samples"] == 579740
    assert payload["measurement_validation_meaning"]


def test_tables_are_written_with_the_columns_asked_for(tmp_path):
    table = write_table(tmp_path / "bands.csv",
                        [{"band_m": "0.018-0.040", "recovered_um": 7.4},
                         {"band_m": "0.018-0.040", "recovered_um": 5.1, "extra": "dropped"}],
                        ["band_m", "recovered_um"])
    text = table.read_text(encoding="utf-8").splitlines()
    assert text[0] == "band_m,recovered_um"
    assert all("extra" not in line for line in text)
    assert len(text) == 3
