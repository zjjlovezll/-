"""The peak count is chosen from the data -- and it only works while the forward law composes.

Round 273 fitted two peaks whose number was given.  This round asks whether the number can be selected
from the data (K gaussians of the declared width, BIC over K = 1..5), and the answer turned out to depend
on something else entirely:

  * on the archived two-peak profile the selector picks 2, and every gate passes (p95 5.26 um);
  * on both three-peak profiles it picks 5, not 3, and the extra gaussians buy the *composition error*
    of the measured share law (rms 0.0165 in share units for two superposed bumps, 0.0317 / 0.0385 for
    three), not a better count.

These tests pin all of that, including the negative result: a future change that makes the three-peak
case select 3 has to show up here as a failure of test 2, and that is the point -- silently "fixing" the
selector must not be possible.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

pytestmark = pytest.mark.corpus

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "peak_count.json"


@pytest.fixture(scope="module")
def report() -> dict:
    assert REPORT.is_file(), f"missing {REPORT}; run scripts/s131_peak_count.py --report"
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_the_selector_counts_two_peaks_when_the_profile_has_two(report):
    two = report["two_peak"]
    assert two["selected_count"] == 2
    assert all(two["gates"].values()), two["gates"]
    assert two["p95_um"] <= 22.0


def test_the_selector_does_not_count_three_peaks_and_that_is_reported(report):
    three = report["three_peak"]
    assert three["selected_count"] == 5
    assert three["gates"]["G-COUNT"] is False
    assert three["gates"]["G-LOC"] is False
    assert report["verdict"].startswith("the selector does not count the peaks")


def test_two_peaks_is_the_best_bic_on_the_two_peak_profile(report):
    bic = {int(key): value for key, value in report["two_peak"]["bic"].items()}
    assert bic[2] < bic[1]
    assert bic[2] < bic[3]
    assert min(bic, key=bic.get) == 2


def test_the_residual_keeps_falling_on_the_three_peak_profile(report):
    """SSE must not plateau on a profile whose law does not compose -- that is the over-selection."""
    bic = {int(key): value for key, value in report["three_peak"]["bic"].items()}
    assert min(bic, key=bic.get) == 5
    assert bic[5] < bic[4] < bic[3] < bic[2] < bic[1]


def test_the_measured_law_does_not_compose_for_superposed_bumps(report):
    composition = report["composition"]
    two = composition["one_set_twopeak"]["share_rms"]
    first = composition["one_set_threepeak"]["share_rms"]
    second = composition["one_set_threepeak_obs"]["share_rms"]
    assert two < 0.02
    assert first > 1.5 * two
    assert second > 1.5 * two
    for row in composition.values():
        assert 0.0 < row["share_rms"] < 0.1


def test_the_declared_profile_and_the_fitted_model_agree_on_the_truth():
    """Pure arithmetic: with the truth parameters, the fitted model must reproduce the truth profile."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import s131_peak_count as peaks

    stations = np.linspace(55.5, 61.5, 401)
    truth = peaks.truth_profile(stations)
    params = [value for centre, amplitude in peaks.PEAKS for value in (amplitude, centre)]
    assert np.allclose(peaks.model(np.asarray(params, dtype=float), stations), truth, atol=1e-9)
