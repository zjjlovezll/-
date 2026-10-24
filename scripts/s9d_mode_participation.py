# -*- coding: utf-8 -*-
"""Which elastic modes actually participate?  Read the modal coordinates, not the accelerations.

The acceleration band check (S9-3) answers "does the acceleration gain energy at 300-400 Hz",
which mixes every mode and the rigid motion together.  The modal coordinates ARE the modes, so
their spectra say directly whether a mode rings at its own frequency (dynamic) or is merely
pushed along by a broadband impact (its peak then lands wherever the impact spectrum happens to
be).

``share`` is the energy within +-20 % of the mode's own frequency over the total alternating
energy.  A high share means resonance; a large rms with a low share means the mode is being swept
by the impact rather than resonating at its own frequency.

Free: it reads histories that other scripts already wrote.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np

from velch.io.history import read_history
from velch.wheel_modes import load_modes

REPO = Path(__file__).resolve().parents[1]
DEFAULT_MODES = REPO / "vehicles" / "modes" / "CRH3C_wheelset_fe.json"
DEFAULT_WORK = Path(r"F:\velch_tmp\s9")
PATTERN = re.compile(r"^axle(?P<axle>\d+)_mode(?P<mode>\d+)_q$")
RUNS = ("out_frog_flexible", "out_straight_flexible")


def participation(path: Path, frequencies: dict[int, float]) -> tuple[float, int, list[dict]]:
    history = read_history(path / "history.csv")
    time = np.asarray(history.data[history.ordering.index("time_s")], dtype=float)
    rate = 1.0 / float(np.mean(np.diff(time)))
    rows: list[dict] = []
    for name in history.ordering:
        match = PATTERN.match(name)
        if match is None:
            continue
        values = np.asarray(history.data[history.ordering.index(name)], dtype=float)
        centre = float(np.mean(values))
        alternating = values - centre
        spectrum = np.abs(np.fft.rfft(alternating * np.hanning(len(alternating))))
        bins = np.fft.rfftfreq(len(alternating), d=1.0 / rate)
        peak = float(bins[int(np.argmax(spectrum))]) if len(spectrum) > 1 else 0.0
        own = frequencies[int(match["mode"])]
        near = (bins >= 0.8 * own) & (bins <= 1.2 * own)
        total = float(np.sum(spectrum ** 2))
        share = float(np.sum(spectrum[near] ** 2) / total) if total > 0 else 0.0
        rows.append({"name": name, "mode": int(match["mode"]), "own_hz": own,
                     "peak_hz": peak, "share": share,
                     "rms": float(np.std(values)), "offset": centre})
    return rate, len(time), rows


def group(rows: list[dict]) -> list[dict]:
    """One line per mode number: the axle that moved most represents it."""

    grouped: dict[int, dict] = {}
    for row in rows:
        entry = grouped.setdefault(row["mode"], {"mode": row["mode"], "own": row["own_hz"],
                                                "rms": 0.0, "peak": row["peak_hz"],
                                                "share": row["share"], "offset": row["offset"]})
        if row["rms"] > entry["rms"]:
            entry.update(rms=row["rms"], peak=row["peak_hz"], share=row["share"],
                         offset=row["offset"])
    return [grouped[mode] for mode in sorted(grouped)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modes", type=Path, default=DEFAULT_MODES)
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--top", type=int, default=14)
    arguments = parser.parse_args()

    modes = load_modes(arguments.modes)
    frequencies = {mode.index: mode.frequency_hz for mode in modes.modes}
    for run in RUNS:
        directory = arguments.work / run
        if not (directory / "history.csv").exists():
            print(f"missing {directory / 'history.csv'}")
            continue
        rate, samples, rows = participation(directory, frequencies)
        print(f"\n== {run} ==  ({samples} samples, {rate:.0f} Hz, "
              f"resolution {rate / samples:.1f} Hz)")
        print("  mode  own Hz   loudest rms (m)  peak Hz  share at own freq  mean offset (m)")
        for entry in group(rows)[:arguments.top]:
            print(f"  {entry['mode']:4d}  {entry['own']:7.2f}  {entry['rms']:15.3e}  "
                  f"{entry['peak']:7.1f}  {entry['share']:17.1%}  {entry['offset']:+15.3e}")
        ranked = sorted(group(rows), key=lambda item: item["rms"], reverse=True)[:5]
        print("  loudest five: " + ", ".join(
            f"mode {entry['mode']} ({entry['own']:.0f} Hz, peak {entry['peak']:.0f} Hz, "
            f"share {entry['share']:.0%}, rms {entry['rms']:.2e} m)" for entry in ranked))
        (arguments.work / f"modes_{run}.json").write_text(json.dumps(rows, indent=2),
                                                          encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
