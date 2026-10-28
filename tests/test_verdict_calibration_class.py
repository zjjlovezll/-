"""A band amplitude may only pass with the excitation class it was calibrated on.

Round 195 measured the gap: a 24-harmonic random record and a pure tone at the same rms differ by
1.14-1.78 in |H| (1.2-5.0 dB), while an eight-fold tone amplitude change moves |H| by 0.17 %.  The
transfer is therefore class-calibrated, and "within 2 dB" without a declared class is not a claim.
These tests make that a construction rule rather than a convention somebody remembers.

The rule is deliberately one-sided: a *failed* layer may report band numbers without a class, because a
degradation path is not a claim and must stay available.
"""

from __future__ import annotations

import pytest

from velch.inverse.verdict import (CALIBRATION_CLASS_FIELDS, LayerResult, Verdict, VerdictError,
                                   calibration_class)

COMPLETE = dict(harmonic_count=24, band_edges_m=(0.10, 0.30), rms_um=8.0, crest_factor=2.28)


def test_a_band_claim_without_a_class_cannot_be_constructed() -> None:
    with pytest.raises(VerdictError) as raised:
        LayerResult(name="L3_inversion", status="passed", metrics={"band_hit_rate": 0.75})
    message = str(raised.value)
    assert "L3_inversion" in message
    assert "band_hit_rate" in message
    for name in CALIBRATION_CLASS_FIELDS:
        assert name in message


def test_a_complete_class_lets_the_claim_through_and_is_written_out() -> None:
    declared = calibration_class(**COMPLETE)
    result = LayerResult(name="L3_inversion", status="passed",
                         metrics={"band_hit_rate": 0.75, "calibration_class": declared})
    metrics = result.as_dict()["metrics"]
    assert metrics["band_hit_rate"] == 0.75
    assert metrics["calibration_class"]["harmonic_count"] == 24
    assert metrics["calibration_class"]["band_edges_m"] == [0.10, 0.30]


def test_a_partial_class_is_rejected_and_names_what_is_missing() -> None:
    partial = calibration_class(**COMPLETE)
    del partial["crest_factor"]
    with pytest.raises(VerdictError) as raised:
        LayerResult(name="L3_inversion", status="passed",
                    metrics={"band_errors_db": [0.1], "calibration_class": partial})
    assert "crest_factor" in str(raised.value)


def test_a_failed_layer_may_report_band_numbers_without_a_class() -> None:
    result = LayerResult(name="L3_inversion", status="failed",
                         metrics={"band_hit_rate": 0.375}, notes="tone calibration loses 1.2-5.0 dB")
    assert result.status == "failed"
    assert result.metrics["band_hit_rate"] == 0.375


@pytest.mark.parametrize("broken", [
    dict(harmonic_count=None),
    dict(band_edges_m=(0.30, 0.10)),
    dict(rms_um=0.0),
    dict(crest_factor=""),
])
def test_calibration_class_refuses_incomplete_or_impossible_values(broken) -> None:
    values = dict(COMPLETE) | broken
    with pytest.raises(VerdictError):
        calibration_class(**values)


def test_the_status_derivation_is_unchanged_by_the_new_rule() -> None:
    verdict = Verdict(record="synthetic: s38/s39 provenance")
    verdict.add(LayerResult(name="L5_acceptance", status="failed",
                            metrics={"detected": False, "bands": 8, "within_gate": 6},
                            notes="6 of 8 bands inside 2 dB"))
    assert verdict.measurement_validation_status == "not_evaluated"

    detected = Verdict(record="real: 75 km/h")
    detected.add(LayerResult(name="L5_acceptance", status="failed",
                             metrics={"detected": 3, "sections": 6},
                             notes="3 of 6 sections"))
    assert detected.measurement_validation_status == "detection_only"
