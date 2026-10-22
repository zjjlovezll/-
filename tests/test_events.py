"""Event descriptors: rise time, decay time, oscillation count."""

from __future__ import annotations

import numpy as np
import pytest

from velch.inverse.events import EventDescriptor, EventError, compare_shapes, describe_event


def _time(duration: float = 1.0, count: int = 512) -> np.ndarray:
    return np.linspace(0.0, duration, count)


def test_symmetric_bump_has_balanced_rise_and_decay() -> None:
    time = _time()
    centre = 0.5
    width = 0.05
    values = -np.exp(-0.5 * ((time - centre) / width) ** 2)
    event = describe_event(time, values)
    assert event.peak == pytest.approx(-1.0, abs=1e-2)
    assert event.amplitude == pytest.approx(-1.0, abs=1e-2)
    assert event.peak_time_s == pytest.approx(centre, abs=2e-3)
    assert event.rise_time_s == pytest.approx(event.decay_time_s, rel=0.35)


def test_fast_rise_slow_decay_is_detected() -> None:
    time = _time(2.0, 1024)
    values = np.where(time < 0.5, 0.0, -np.exp(-(time - 0.5) / 0.4))
    event = describe_event(time, values)
    assert event.baseline == pytest.approx(0.0, abs=1e-12)
    assert event.rise_time_s < event.decay_time_s / 5.0


def test_baseline_uses_the_quiet_head() -> None:
    time = _time()
    values = np.full(time.size, 7.0)
    values[200:260] = -3.0
    event = describe_event(time, values)
    assert event.baseline == pytest.approx(7.0)
    assert event.amplitude == pytest.approx(-10.0)


def test_oscillation_count_counts_sign_changes() -> None:
    time = _time(1.0, 1024)
    values = np.sin(2.0 * np.pi * 20.0 * time) * np.exp(-3.0 * time)
    event = describe_event(time, values, index=13)
    assert event.oscillation_count >= 1


def test_window_limits_the_decay_search() -> None:
    time = _time(4.0, 2048)
    values = np.where(time < 0.5, 0.0, -np.exp(-(time - 0.5) / 2.0))
    full = describe_event(time, values)
    short = describe_event(time, values, window_s=0.25)
    assert short.decay_time_s <= 0.25 + 1e-9
    assert short.decay_time_s < full.decay_time_s
    assert short.window_s == pytest.approx(0.25, abs=0.01)


def test_flat_record_is_rejected() -> None:
    with pytest.raises(EventError):
        describe_event(_time(), np.zeros(512))


def test_bad_inputs_rejected() -> None:
    with pytest.raises(EventError):
        describe_event(_time(1.0, 4), np.ones(4))
    with pytest.raises(EventError):
        describe_event(_time(), np.ones(511))
    with pytest.raises(EventError):
        describe_event(_time(), np.linspace(0, 1, 512), baseline_fraction=0.0)
    with pytest.raises(EventError):
        describe_event(_time(), np.linspace(0, 1, 512), threshold_fraction=1.0)
    with pytest.raises(EventError):
        describe_event(_time()[::-1].copy(), np.linspace(0, 1, 512))


def test_compare_shapes_uses_durations_only() -> None:
    reference = EventDescriptor(baseline=0.0, peak=-1.0, amplitude=-1.0, peak_time_s=0.1,
                                rise_time_s=0.002, decay_time_s=0.05, oscillation_count=0,
                                window_s=1.0)
    candidate = EventDescriptor(baseline=0.0, peak=-300.0, amplitude=-300.0, peak_time_s=0.2,
                                rise_time_s=0.004, decay_time_s=0.10, oscillation_count=1,
                                window_s=1.0)
    ratios = compare_shapes(reference, candidate)
    assert ratios["rise_ratio"] == pytest.approx(2.0)
    assert ratios["decay_ratio"] == pytest.approx(2.0)
    assert "amplitude_ratio_not_comparable" in ratios


def test_report_round_trips() -> None:
    event = describe_event(_time(), -np.exp(-0.5 * ((_time() - 0.5) / 0.05) ** 2))
    report = event.report()
    assert set(report) == {"baseline", "peak", "amplitude", "peak_time_s", "rise_time_s",
                           "decay_time_s", "oscillation_count", "window_s"}
    assert "rise" in event.summary(unit="kN", label="CH01")
