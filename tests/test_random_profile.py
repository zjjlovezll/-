"""A random profile: a non-parametric estimator, judged by the gates that were already there.

Rounds 273-276 sized profiles made of a few declared bumps.  A random irregularity is not that: the
count is neither known nor meaningful, so `scripts/s134_random_profile.py` inverts one height per usable
station through the measured law with a second-difference penalty.  This module pins:

  * the seeded profile (reproducible, inside the observable band, separated);
  * the gates (22 um absolute, 16.7 um null, 0.90 correlation, 0.20 m peak, 0.02 share residual) --
    none of them relaxed relative to the earlier rounds;
  * that `judge` actually fails a shifted answer instead of always agreeing.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s134_random_profile as random_profile  # noqa: E402

pytestmark = pytest.mark.corpus


def test_the_seeded_profile_is_reproducible_and_inside_the_observable_band() -> None:
    peaks = random_profile.truth_peaks()
    again = random_profile.truth_peaks()
    assert len(peaks) == random_profile.PEAK_COUNT == 6
    assert np.allclose(np.asarray(peaks, dtype=float), np.asarray(again, dtype=float), rtol=0.0, atol=0.0)
    centres = [centre for centre, _ in peaks]
    assert all(random_profile.CENTRE_LO_M <= centre <= random_profile.CENTRE_HI_M for centre in centres)
    assert min(np.diff(sorted(centres))) >= random_profile.MIN_SEPARATION_M
    amplitudes = [amplitude for _, amplitude in peaks]
    assert all(random_profile.AMPLITUDE_LO_UM <= amplitude <= random_profile.AMPLITUDE_HI_UM
               for amplitude in amplitudes)


def test_each_component_dominates_its_own_centre() -> None:
    """The sum must be the profile the report scores against, not a different shape."""
    peaks = random_profile.truth_peaks()
    for index, (centre, amplitude) in enumerate(peaks):
        others = [other_amplitude * np.exp(-0.5 * ((centre - other_centre) / random_profile.WIDTH_M) ** 2)
                  for other_index, (other_centre, other_amplitude) in enumerate(peaks) if other_index != index]
        value = float(random_profile.profile_um(np.asarray([centre]))[0])
        assert value == pytest.approx(amplitude + sum(others), rel=1e-9)
        # At 0.35 m width the neighbours are ~1.4 sigma away, so their tails are NOT negligible: that is
        # exactly the superposition this round is about.  What must hold is that the station's own
        # component is still the largest single contribution.
        assert amplitude >= max(others)
        assert sum(others) <= 1.2 * amplitude


def test_the_gates_are_the_ones_the_earlier_rounds_used() -> None:
    assert random_profile.ABSOLUTE_LIMIT_UM == 22.0
    assert random_profile.NULL_LIMIT_UM == 16.7
    assert random_profile.CORRELATION_LIMIT == 0.90
    assert random_profile.PEAK_LIMIT_M == 0.20
    assert random_profile.RESIDUAL_LIMIT == 0.02
    assert random_profile.LAMBDA == 1.0e-4 and random_profile.WIDTH_M == 0.35


def test_judge_accepts_a_perfect_answer_and_rejects_a_shifted_one() -> None:
    stations = np.linspace(57.5, 63.5, 601)
    truth = random_profile.profile_um(stations)
    perfect = random_profile.judge(stations, truth, 0.0)
    assert perfect["p95_um"] < 1e-9 and perfect["correlation"] == pytest.approx(1.0)
    assert perfect["peak_error_m"] < 1e-9 and all(perfect["gates"].values())

    shifted = random_profile.judge(stations, np.interp(stations - 0.5, stations, truth), 0.0)
    assert shifted["peak_error_m"] > random_profile.PEAK_LIMIT_M
    assert not shifted["gates"]["G-PEAK"]
    assert not shifted["passed"]


def test_judge_windows_on_the_truth_it_scores_against() -> None:
    stations = np.linspace(57.5, 63.5, 601)
    truth = random_profile.profile_um(stations)
    zeros = random_profile.judge(stations, np.zeros_like(stations), 0.05)
    assert zeros["window_stations"] < stations.size, "the window must exclude the quiet stations"
    assert zeros["p95_um"] > random_profile.ABSOLUTE_LIMIT_UM
    assert not zeros["gates"]["G-ABS"] and not zeros["gates"]["G-RES"]


def test_the_report_exists_and_says_what_it_measured() -> None:
    if not random_profile.REPORT.exists():
        pytest.skip("the random-profile report has not been produced yet")
    payload = json.loads(random_profile.REPORT.read_text(encoding="utf-8"))
    assert payload["route"] == random_profile.ROUTE
    assert payload["seed"] == random_profile.SEED
    assert len(payload["truth"]) == random_profile.PEAK_COUNT
    gates = payload["gates"]
    assert set(gates) == {"G-ABS", "G-CORR", "G-PEAK", "G-RES", "G-NULL"}
    assert payload["passed"] == all(gates.values())
    assert "verdict" in payload and payload["verdict"]
    assert payload["non_parametric"]["usable_stations"] > 100
    # the parametric pipeline must be reported even when it is worse
    assert "selected" in payload["parametric"] and "peaks" in payload["parametric"]
