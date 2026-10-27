# -*- coding: utf-8 -*-
"""Compare the acceleration channels of a rigid and a flexible wheelset (S9-3).

The question this answers is narrow and checkable: once the tread deforms, does the axle-box
acceleration gain energy in the band the 陈嘉胤 thesis reports for a flexible wheelset (345 / 378 Hz
from wheel-disc modes), and does the rigid model simply not have it?

It reads the histories that ``scripts/s9_compare.py`` already wrote, so it costs no simulation.
Both runs must share the same output step: the Nyquist limit of the comparison is one over twice
that step, and a "missing" band is more often an undersampled band than absent physics.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from velch.io.history import read_history

DEFAULT_WORK = Path(r"F:\velch_tmp\s9")
# The frog window runs the inline 35-dof vehicle, which has no axle-box bodies, so the same
# comparison falls back to the wheelset channel there.  Reporting which channel was actually
# read is part of the result: an axle-box number and a wheelset number are not interchangeable.
AXLE_BOX = "axle1_box_left_z_acc_m_per_s2"
WHEELSET = "axle1_z_acc_m_per_s2"
CARBODY = "carbody_z_acc_m_per_s2"
ELASTIC_BAND = (300.0, 400.0)
THESIS_BAND = (340.0, 390.0)


def series(history, name: str) -> np.ndarray:
    return np.asarray(history.data[history.ordering.index(name)], dtype=float)


def spectrum(values: np.ndarray, rate_hz: float) -> tuple[np.ndarray, np.ndarray]:
    """One-sided amplitude spectrum with a Hann window and the mean removed."""
    centred = values - float(np.mean(values))
    window = np.hanning(len(centred))
    scaled = centred * window
    amplitudes = np.fft.rfft(scaled)
    frequencies = np.fft.rfftfreq(len(centred), d=1.0 / rate_hz)
    # A Hann window spreads each line over three bins, so the coherent gain is the sum of the
    # window divided by the number of samples: 0.5 for Hann.  Without it every amplitude is
    # half of the truth, which is exactly the kind of factor that reads as "the model is weak".
    gain = float(np.sum(window)) / len(window)
    magnitude = 2.0 * np.abs(amplitudes) / (len(centred) * gain)
    return frequencies, magnitude


def band_rms(frequencies: np.ndarray, magnitude: np.ndarray, low: float, high: float) -> float:
    mask = (frequencies >= low) & (frequencies <= high)
    if not np.any(mask):
        return 0.0
    return float(np.sqrt(0.5 * np.sum(magnitude[mask] ** 2)))


def strongest(frequencies: np.ndarray, magnitude: np.ndarray, low: float, high: float,
              count: int = 5) -> list[tuple[float, float]]:
    mask = (frequencies >= low) & (frequencies <= high)
    if not np.any(mask):
        return []
    band = np.where(mask)[0]
    order = band[np.argsort(magnitude[band])[::-1]]
    kept: list[tuple[float, float]] = []
    for index in order:
        if all(abs(frequencies[index] - other) > 5.0 for other, _ in kept):
            kept.append((float(frequencies[index]), float(magnitude[index])))
        if len(kept) >= count:
            break
    return kept


def describe(path: Path, channel: str) -> dict[str, object]:
    history = read_history(path / "history.csv")
    time = series(history, "time_s")
    rate = 1.0 / float(np.mean(np.diff(time)))
    values = series(history, channel)
    frequencies, magnitude = spectrum(values, rate)
    return {
        "run": path.name,
        "channel": channel,
        "rate_hz": rate,
        "samples": int(len(values)),
        "rms": float(np.std(values)),
        "peak_g": float(np.max(np.abs(values)) / 9.81),
        "elastic_band_rms": band_rms(frequencies, magnitude, *ELASTIC_BAND),
        "thesis_band_rms": band_rms(frequencies, magnitude, *THESIS_BAND),
        "strongest": strongest(frequencies, magnitude, *ELASTIC_BAND),
        "spectrum": (frequencies, magnitude),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--window", default="straight",
                        help="which pair of runs to read: straight or frog")
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    report: dict[str, object] = {"work": str(arguments.work), "channels": {}}
    for channel in (AXLE_BOX, CARBODY):
        rows = []
        for variant in ("rigid", "flexible"):
            directory = arguments.work / f"out_{arguments.window}_{variant}"
            if not (directory / "history.csv").exists():
                print(f"missing {directory / 'history.csv'} - run scripts/s9_compare.py first")
                return 2
            probe = read_history(directory / "history.csv")
            chosen = channel if channel in probe.ordering else (
                WHEELSET if WHEELSET in probe.ordering else CARBODY)
            if chosen != channel:
                print(f"  ({channel} absent in {directory.name}; reading {chosen})")
            row = describe(directory, chosen)
            spectrum_values = row.pop("spectrum")
            rows.append(row)
            if chosen == channel:
                frequencies, magnitude = spectrum_values
                np.savez(arguments.work / f"spectrum_{arguments.window}_{variant}.npz",
                         frequencies=frequencies, magnitude=magnitude)
        rigid, flexible = rows
        # Label the table with the channel that was actually read, not the one that was asked for:
        # the first version printed the requested name over rows from a different channel.
        print(f"\n{rigid['channel']}  ({rigid['rate_hz']:.0f} Hz, {rigid['samples']} samples, "
              f"resolution {rigid['rate_hz'] / rigid['samples']:.1f} Hz)")
        print(f"  {'run':10s} {'rms':>9s} {'peak g':>8s} {'300-400 rms':>13s} {'340-390 rms':>13s}")
        for row in rows:
            print(f"  {row['run']:10s} {row['rms']:9.4f} {row['peak_g']:8.2f} "
                  f"{row['elastic_band_rms']:13.5f} {row['thesis_band_rms']:13.5f}")
        ratio = (flexible["elastic_band_rms"] / rigid["elastic_band_rms"]
                 if rigid["elastic_band_rms"] > 0 else float("inf"))
        print(f"  flexible/rigid in 300-400 Hz: {ratio:.3f}")
        for row in rows:
            peaks = ", ".join(f"{frequency:.1f} Hz ({value:.4f})"
                              for frequency, value in row["strongest"])
            print(f"  {row['run']:10s} strongest: {peaks or 'none'}")
        report["channels"][channel] = {"rows": rows, "ratio": ratio}

    destination = arguments.out or (arguments.work / f"acceleration_{arguments.window}.json")
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
