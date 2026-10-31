"""The residual is static, so the quasi-static family was not the mistake.

The last untested candidate was that the measurement itself is dynamic: a 0.35 m feature passes in 16 ms at
80 km/h.  Measured on archived runs only: the six-component residual puts 89 % of its energy below 20 Hz,
peaks at 5.2 Hz and has a 0.00 mm cross-correlation lag, so the dynamics is not the explanation and the next
candidate stays a per-station contact model.

The two-peak run is the counterweight that keeps this honest: 82.4 % of its residual energy is above 20 Hz,
but that residual is 0.0155 rms against the six-component 0.1317, so "static" describes the hard case, not
every case.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s139_residual_dynamics as dynamics  # noqa: E402


def test_a_pure_sinusoid_at_5hz_counts_as_static() -> None:
    times = np.arange(0.0, 0.6, 5.0e-4)
    panel = {"residual": 0.01 * np.sin(2.0 * np.pi * 5.0 * times), "times": times,
             "station": 58.0 + 22.222 * times, "share": np.zeros_like(times),
             "predicted": np.zeros_like(times)}
    spectrum = dynamics._spectrum(panel)
    assert spectrum["peak_hz"] == pytest.approx(5.0, abs=1.0)
    assert spectrum["above_fraction"] < 0.05


def test_a_pure_sinusoid_at_80hz_counts_as_dynamic() -> None:
    times = np.arange(0.0, 0.6, 5.0e-4)
    panel = {"residual": 0.01 * np.sin(2.0 * np.pi * 80.0 * times), "times": times,
             "station": 58.0 + 22.222 * times, "share": np.zeros_like(times),
             "predicted": np.zeros_like(times)}
    spectrum = dynamics._spectrum(panel)
    assert spectrum["peak_hz"] == pytest.approx(80.0, abs=2.0)
    assert spectrum["above_fraction"] > 0.95


def test_the_lag_is_zero_for_aligned_signals() -> None:
    stations = 50.0 + 0.11 * np.arange(200)
    signal = np.sin(0.05 * stations)
    panel = {"predicted": signal, "share": signal.copy(), "station": stations}
    assert abs(dynamics._lag_mm(panel)) < 1.0


@pytest.mark.corpus
def test_the_hard_case_residual_is_static() -> None:
    if not dynamics.REPORT.exists():
        pytest.skip("the residual-dynamics test has not been produced yet")
    report = json.loads(dynamics.REPORT.read_text(encoding="utf-8"))
    rows = {row["route"]: row for row in report["rows"]}

    holdout = rows["one_set_random"]
    assert holdout["above_20hz_fraction"] < 0.20
    assert holdout["peak_hz"] < 10.0
    assert abs(holdout["lag_mm"]) < 2.0
    assert report["holdout_is_dynamic"] is False

    # the counterweight: a well-recovered profile can still carry high-frequency detail, and its rms is small
    two_peak = rows["one_set_twopeak"]
    assert two_peak["above_20hz_fraction"] > 0.50
    assert two_peak["residual_rms"] < 0.05 < holdout["residual_rms"]


@pytest.mark.corpus
def test_the_verdict_keeps_the_quasi_static_family() -> None:
    if not dynamics.REPORT.exists():
        pytest.skip("the residual-dynamics test has not been produced yet")
    report = json.loads(dynamics.REPORT.read_text(encoding="utf-8"))
    verdict = report["verdict"]
    assert "static" in verdict
    assert "quasi-static family is right" in verdict
    assert "recovered" not in verdict and "amplitude" not in verdict
