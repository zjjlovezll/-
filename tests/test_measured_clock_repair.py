"""Clock repair for campaign exports whose timestamps repeat or step backwards."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from velch.io.measured import CH01_CALIBRATION_FACTOR, MIN_SAMPLES, MeasuredIOError, read_channel


def _write_channel(folder: Path, channel: int, time: np.ndarray, value: np.ndarray) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    index = np.arange(time.shape[0], dtype=float)
    data = np.column_stack((index, time, value))
    np.savetxt(folder / f"V30KMH27#{channel}.txt", data, fmt="%.9f")


def test_strict_reader_rejects_a_repeated_timestamp(tmp_path: Path) -> None:
    rate = 5120.0
    time = np.arange(MIN_SAMPLES + 10, dtype=float) / rate
    time[5] = time[4]  # the acquisition buffer repeated one stamp
    _write_channel(tmp_path, 1, time, np.zeros_like(time))

    with pytest.raises(MeasuredIOError, match="not strictly increasing"):
        read_channel(tmp_path, 1)


def test_repair_drops_only_the_offending_samples(tmp_path: Path) -> None:
    rate = 5120.0
    stamps = np.arange(MIN_SAMPLES + 20, dtype=float)
    time = stamps / rate
    time[5] = time[4]          # one repeated stamp
    time[9] = time[8] - 1e-4   # one backward step
    values = np.linspace(0.0, 1.0, time.shape[0])
    _write_channel(tmp_path, 1, time, values)

    repaired_time, repaired_value = read_channel(tmp_path, 1, repair_clock=True)

    assert repaired_time.shape[0] == time.shape[0] - 2
    assert np.all(np.diff(repaired_time) > 0.0)
    # the recorded stamps survive as recorded: a dropped sample leaves a two-step hole,
    # it is never re-indexed onto a grid that would invent samples
    steps = np.diff(repaired_time)
    assert np.isclose(steps.min(), 1.0 / rate)
    assert np.count_nonzero(np.isclose(steps, 2.0 / rate)) == 2
    # the surviving samples keep their own amplitudes and stay in order
    kept = [i for i in range(time.shape[0]) if i not in (5, 9)]
    assert np.allclose(repaired_value, values[kept] * CH01_CALIBRATION_FACTOR)
    assert np.all(np.diff(repaired_value) > 0.0)


def test_repair_keeps_the_uncalibrated_channel_scale(tmp_path: Path) -> None:
    rate = 5120.0
    time = np.arange(MIN_SAMPLES + 10, dtype=float) / rate
    time[3] = time[2]
    values = np.full(time.shape[0], 7.0)
    _write_channel(tmp_path, 2, time, values)

    _, repaired = read_channel(tmp_path, 2, repair_clock=True)
    assert np.allclose(repaired, 7.0)  # CH02 carries no calibration factor
