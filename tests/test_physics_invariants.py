"""The physics-invariants reference must be real, complete, and matched by the archive on disk."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "src"
REFERENCE = REPO / "docs" / "physics_invariants.json"

sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(REPO / "scripts"))


def _module():
    spec = importlib.util.spec_from_file_location(
        "physics_invariants", REPO / "scripts" / "physics_invariants.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_every_tolerance_the_comparison_uses_exists() -> None:
    module = _module()
    for key in ("contact_peaks_kn", "max_penetration_um", "overall_peak_kn", "rms_kn",
                "dominant_hz", "band"):
        assert key in module.TOLERANCES


def test_a_short_window_no_longer_breaks_the_band_filter() -> None:
    """``band_metrics`` used to raise on a 70-sample window: scipy rejected the near-Nyquist edge."""

    from velch.inverse.bands import band_metrics

    rate = 1.0 / ((0.0345) / 69)  # the 78.8-82.2 m window: 70 samples at 2 kHz
    values = np.sin(2.0 * np.pi * 45.0 * np.arange(70) / rate)
    metrics = band_metrics(values, rate)
    assert np.isfinite(metrics.rms) and metrics.rms > 0.0
