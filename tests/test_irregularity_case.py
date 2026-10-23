"""Irregularity through the case loader: applied where the surface is sampled (corpus needed)."""

from __future__ import annotations

import numpy as np
import pytest

from velch.data_root import case_dir
from velch.irregularity import read_tre
from velch.vehicle import load_vehicle_case

pytestmark = pytest.mark.corpus

TRE = r"H:\不平顺\tre.tre"
MISSING = not __import__("pathlib").Path(TRE).is_file()


def _case(name: str):
    path = case_dir() / name
    if not path.is_file():
        pytest.skip(f"{name} not present in the corpus root")
    return load_vehicle_case(path)


def test_a_case_without_the_block_has_no_record():
    case = _case("case_frog_N_strip05.json")
    assert case.irregularity is None


def _mileages(body, window=(69.0, 74.0)):
    """Three mileages inside both the body's station coverage and the excitation window."""

    lo = max(window[0], float(body.series.lowest_m)) + 0.25
    hi = min(window[1], float(body.series.highest_m)) - 0.25
    if hi <= lo:
        return []
    return [lo, 0.5 * (lo + hi), hi]


def test_zero_amplitude_reproduces_the_untouched_surface_exactly():
    plain = _case("case_frog_N_strip05.json")
    zero = _case("case_irr_zero.json")
    assert zero.irregularity is not None
    compared = 0
    for rail_plain, rail_zero in zip(plain.rails, zero.rails):
        for body_plain, body_zero in zip(rail_plain.bodies, rail_zero.bodies):
            for s_m in _mileages(body_plain):
                left = body_plain.series.sample(s_m).profile
                right = body_zero.series.sample(s_m).profile
                assert np.array_equal(left.y_m, right.y_m)
                assert np.array_equal(left.z_m, right.z_m)
                compared += 1
    assert compared >= 6, "no body covered the excitation window; the test proved nothing"


@pytest.mark.skipif(MISSING, reason=f"{TRE} not on this machine")
def test_full_amplitude_shifts_each_rail_by_the_recorded_sample():
    track = read_tre(TRE)
    cut = _case("case_irr_full.json")
    plain = _case("case_frog_N_strip05.json")
    half_gauge = abs(cut.wheels[0].lateral_offset_m)
    checked = 0
    for rail_zero, rail_full in zip(plain.rails, cut.rails):
        side = "left" if rail_full.id.endswith("left") else "right"
        sign = -1.0 if side == "left" else 1.0
        for s_m in _mileages(rail_zero.bodies[0]):
            lateral, vertical, roll, gauge = track.at(s_m)
            expected_dz = vertical + sign * roll * half_gauge
            expected_dy = lateral + sign * 0.5 * gauge
            before = rail_zero.bodies[0].series.sample(s_m).profile
            after = rail_full.bodies[0].series.sample(s_m).profile
            assert np.allclose(after.z_m - before.z_m, expected_dz, atol=1e-12)
            assert np.allclose(after.y_m - before.y_m, expected_dy, atol=1e-12)
            checked += 1
    assert checked >= 6


def test_the_case_records_what_was_applied_and_from_where():
    case = _case("case_irr_full.json")
    record = case.irregularity or {}
    assert record["channels"] == ["lateral", "vertical", "roll", "gauge"]
    assert record["start_m"] == pytest.approx(69.0)
    assert record["end_m"] == pytest.approx(74.0)
    assert record["fade_m"] == pytest.approx(0.25)
    assert record["scale"] == pytest.approx(1.0)
    assert len(record["sha256"]) == 64
    assert "half-cosine" in record["fade_shape"]
    assert "centreline" in record["applied_at"]
