"""Resolution, not just rank: what a single-point observable cannot tell you."""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.inverse.identifiability import (
    IdentifiabilityError,
    Sensitivity,
    Verdict,
    analyse,
)


def _waveform(doubling: float = 1.0) -> Sensitivity:
    rng = np.random.default_rng(7)
    column = rng.normal(0.0, 1.0, 64) * doubling
    return Sensitivity(("rail_k_z",), column.reshape(-1, 1), (1.0,) * 64,
                       observable="waveform")


def _peak() -> Sensitivity:
    return Sensitivity(("rail_k_z",), np.array([[1.0e-3]]), (1.0,), observable="peak")


def test_resolution_is_inverse_column_norm() -> None:
    verdict = analyse(_waveform())
    norm = float(np.linalg.norm(np.random.default_rng(7).normal(0.0, 1.0, 64)))
    assert verdict.resolution["rail_k_z"] == pytest.approx(1.0 / norm, rel=1e-9)


def test_doubling_sensitivity_halves_resolution() -> None:
    base = analyse(_waveform(1.0)).resolution["rail_k_z"]
    doubled = analyse(_waveform(2.0)).resolution["rail_k_z"]
    assert doubled == pytest.approx(base / 2.0, rel=1e-9)


def test_peak_observable_is_flagged() -> None:
    verdict = analyse(_peak())
    assert verdict.observable == "peak"
    assert any("single-point extremum" in note for note in verdict.notes)


def test_coarse_resolution_is_reported_in_percent() -> None:
    verdict = analyse(_peak())
    assert verdict.resolution["rail_k_z"] == pytest.approx(1000.0, rel=1e-12)
    assert any("poorly resolved" in note for note in verdict.notes)


def test_waveform_passes_without_warning() -> None:
    verdict = analyse(_waveform(4.0))
    assert verdict.identifiable["rail_k_z"] is True
    assert not any("poorly resolved" in note for note in verdict.notes)
    assert not any("single-point" in note for note in verdict.notes)


def test_waveform_resolution_beats_peak() -> None:
    assert analyse(_waveform()).resolution["rail_k_z"] * 100.0 < \
        analyse(_peak()).resolution["rail_k_z"]


def test_blank_observable_rejected() -> None:
    with pytest.raises(IdentifiabilityError):
        Sensitivity(("theta",), np.zeros((2, 1)), (1.0, 1.0), observable="   ")


def test_summary_mentions_observable() -> None:
    text = analyse(_waveform()).summary()
    assert "observable waveform" in text


def test_verdict_defaults_keep_old_construction_valid() -> None:
    verdict = Verdict(names=("a",), singular_values=(1.0,), condition_number=1.0, rank=1,
                      normalised_sensitivity={"a": 1.0}, identifiable={"a": True},
                      coverage={"a": "observed"})
    assert verdict.resolution == {}
    assert math.isinf(verdict.condition_number) is False
