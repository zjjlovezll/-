"""Force-spectrum comparison between two runs on the same mileage axis.

The point-contact model rings at ~194 Hz where the vendor's patch contact does
not. This tool separates the two possible sources of that ring: a real
single-point contact on the wing rail, or the contact point snapping from node
to node on the sampling grid. If the ringing disappears when the geometry policy
is refined, it was numerical; if the band energy is unchanged, it is physical.

Usage:
    python -X utf8 cmp_spectrum.py <dir_a> <dir_b> [--column axle1_right_normal_n]
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

BANDS = ((0.0, 150.0), (150.0, 250.0), (250.0, 400.0), (400.0, 700.0))


def load(path: Path, column: str) -> tuple[np.ndarray, np.ndarray]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    t = np.array([float(row["time_s"]) for row in rows])
    f = np.array([float(row[column]) for row in rows])
    return t, f


def spectrum(t: np.ndarray, f: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    dt = float(np.median(np.diff(t)))
    signal = f - float(np.mean(f))
    window = np.hanning(signal.size)
    amplitude = np.abs(np.fft.rfft(signal * window)) * 2.0 / np.sum(window)
    freq = np.fft.rfftfreq(signal.size, dt)
    return freq, amplitude


def describe(name: str, t: np.ndarray, f: np.ndarray) -> dict:
    freq, amplitude = spectrum(t, f)
    power = amplitude ** 2
    total = float(np.sum(power[1:]))
    rows = []
    for low, high in BANDS:
        select = (freq >= low) & (freq < high)
        share = float(np.sum(power[select])) / total if total > 0 else 0.0
        # Absolute RMS in the band. The share alone is misleading: if the whole
        # ring is damped, the share of the dominant band can stay put while its
        # amplitude falls, which is exactly what a softer contact law does.
        band_rms = float(np.sqrt(2.0 * np.sum(power[select]) / power.size))
        rows.append((f"{low:.0f}-{high:.0f} Hz", share, band_rms))
    peak = int(np.argmax(amplitude[1:]) + 1) if amplitude.size > 1 else 0
    return {
        "name": name,
        "peak_force_kn": float(np.max(f)) / 1e3,
        "min_force_kn": float(np.min(f)) / 1e3,
        "ac_rms_n": float(np.std(f)),
        "dominant_hz": float(freq[peak]),
        "band_shares": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", help="output directories")
    parser.add_argument("--column", default="axle1_right_normal_n")
    args = parser.parse_args()
    reports = []
    for run in args.runs:
        directory = Path(run)
        t, f = load(directory / "history.csv", args.column)
        report = describe(directory.name, t, f)
        reports.append(report)
        print(f"{report['name']:22s} peak {report['peak_force_kn']:7.2f} kN  "
              f"rms {report['ac_rms_n']:8.1f} N  dominant {report['dominant_hz']:6.1f} Hz")
        for label, share, band_rms in report["band_shares"]:
            print(f"    {label:12s} {share * 100:5.1f}%   {band_rms / 1e3:6.2f} kN rms")
    Path("cmp_spectrum.json").write_text(json.dumps(reports, indent=1, ensure_ascii=False),
                                         encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
