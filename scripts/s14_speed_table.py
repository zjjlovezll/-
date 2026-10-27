"""L2, first half: the measured reference table, one row per recorded speed.

The 95 % claim in the goal is defined on detection, not on amplitude, and the pipeline may not
extrapolate between speeds.  So the first thing L2 owes is a table that says, for **each recorded
speed**, what the corrugation looks like: the narrow band that carries it, its centre frequency, and
the wavelength that frequency corresponds to at that file's own speed.

The wavelength is the interesting column.  If the paper's constant-wavelength hypothesis holds, the
four speeds must agree on wavelength while their frequencies scale with speed; if they do not agree,
no single band table may be shared across speeds and L3 has to keep one per speed.

This layer writes ``bands.csv`` (per speed, per band) and leaves the calibration of any gain to L3,
where the model enters and superposition can be tested.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

import s13_admission as gate

RATE_HZ = gate.RATE_HZ
WINDOW_M = 25.0
HOP_M = 5.0
BAND_MM = (18.0, 40.0)
MIN_HZ, MAX_HZ = 150.0, 1800.0


def windows(position_m: np.ndarray, *, window_m: float, hop_m: float) -> list[tuple[int, int]]:
    start = float(position_m[0])
    stop = float(position_m[-1])
    edges: list[tuple[int, int]] = []
    cursor = start
    while cursor + window_m <= stop:
        first = int(np.searchsorted(position_m, cursor))
        last = int(np.searchsorted(position_m, cursor + window_m))
        if last - first > 32:
            edges.append((first, last))
        cursor += hop_m
    return edges


def dominant_line(signal: np.ndarray, rate_hz: float) -> tuple[float, float]:
    """Strongest narrow line in the search band, as (frequency_hz, prominence_db)."""

    length = signal.size
    if length < 64:
        return 0.0, 0.0
    window = np.hanning(length)
    spectrum = np.abs(np.fft.rfft(signal * window)) ** 2
    frequencies = np.fft.rfftfreq(length, d=1.0 / rate_hz)
    inside = (frequencies >= MIN_HZ) & (frequencies <= min(MAX_HZ, 0.95 * rate_hz))
    if not np.any(inside):
        return 0.0, 0.0
    band = np.where(inside)[0]
    peak = int(band[int(np.argmax(spectrum[band]))])
    floor = float(np.median(spectrum[band]))
    prominence = 10.0 * math.log10(max(spectrum[peak], 1e-30) / max(floor, 1e-30))
    return float(frequencies[peak]), prominence


def analyse(path: Path) -> dict:
    data = gate.load(path)
    time = gate._flat(data.get("Vi_t"))
    position_m = gate._flat(data.get("Vi_pks")) * 1000.0
    speed_m_s = gate._flat(data.get("Vi_Speed")) / 3.6
    channels = data.get("Vi_y")
    if time is None or position_m is None or channels is None or channels.ndim != 2:
        raise SystemExit(f"{path.name}: not a usable acceleration record")
    rate = float(1.0 / np.median(np.diff(time)))

    speeds, frequencies, wavelengths, prominences = [], [], [], []
    for first, last in windows(position_m, window_m=WINDOW_M, hop_m=HOP_M):
        local_speed = float(np.mean(speed_m_s[first:last]))
        if local_speed < 3.0:
            continue
        for column in range(channels.shape[1]):
            frequency, prominence = dominant_line(channels[first:last, column], rate)
            if frequency <= 0.0 or prominence < 6.0:
                continue
            speeds.append(local_speed)
            frequencies.append(frequency)
            wavelengths.append(1000.0 * local_speed / frequency)   # mm
            prominences.append(prominence)

    if not speeds:
        return {"file": path.name, "windows": 0}
    frequencies = np.asarray(frequencies)
    wavelengths = np.asarray(wavelengths)
    inside = (wavelengths >= BAND_MM[0]) & (wavelengths <= BAND_MM[1])
    return {
        "file": path.name,
        "mean_speed_kmh": float(np.mean(np.asarray(speeds)) * 3.6),
        "windows": int(len(speeds)),
        "median_frequency_hz": float(np.median(frequencies)),
        "median_wavelength_mm": float(np.median(wavelengths)),
        "in_band_fraction": float(np.mean(inside)),
        "median_frequency_in_band_hz": float(np.median(frequencies[inside])) if np.any(inside) else None,
        "median_wavelength_in_band_mm": float(np.median(wavelengths[inside])) if np.any(inside) else None,
        "median_prominence_db": float(np.median(prominences)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(r"F:\ai道岔状态反演辨识\75kmh数据"))
    parser.add_argument("--output", type=Path, default=Path(r"F:\velch_tmp\verdict\bands.csv"))
    parser.add_argument("--summary", type=Path, default=Path(r"F:\velch_tmp\verdict\speed_table.json"))
    args = parser.parse_args(argv)

    files = sorted(args.data.glob("*.mat"))
    if not files:
        raise SystemExit(f"no .mat files under {args.data}")
    rows = []
    for path in files:
        row = analyse(path)
        rows.append(row)
        if row["windows"]:
            print(
                f"{row['file']:22s} {row['mean_speed_kmh']:6.1f} km/h  "
                f"median f {row['median_frequency_hz']:7.1f} Hz  "
                f"median lambda {row['median_wavelength_mm']:6.1f} mm  "
                f"in 18-40 mm {row['in_band_fraction']:5.1%}  "
                f"prominence {row['median_prominence_db']:4.1f} dB"
            )
        else:
            print(f"{row['file']:22s} no usable window")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    args.summary.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")

    usable = [row for row in rows if row.get("windows")]
    if len(usable) < 2:
        # One recorded speed is a real limitation, not a verdict: the table is published with the
        # row it has and the missing files are named, so nobody reads a cross-speed claim into it.
        found = sorted(path.name for path in files)
        print(f"only one usable speed file on this machine: {', '.join(found)}")
        print("the 60 / 50 / 40 km/h records named in the README are NOT present, so no")
        print("cross-speed wavelength comparison is possible here.")
        print(f"verdict: SINGLE-SPEED (not a pass, not a failure)  -> {args.output}")
        return 0
    wavelengths = [row["median_wavelength_mm"] for row in usable]
    spread = (max(wavelengths) - min(wavelengths)) / float(np.mean(wavelengths))
    agree = spread <= 0.25
    print(f"wavelength spread across speeds: {spread:.1%} -> {'consistent' if agree else 'NOT consistent'}")
    print(f"verdict: {'PASS' if agree else 'FAIL'}  -> {args.output}")
    return 0 if agree else 2


if __name__ == "__main__":
    raise SystemExit(main())
