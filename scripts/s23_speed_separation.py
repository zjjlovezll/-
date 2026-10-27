"""Separate vehicle modes from track periodicity inside one record, using its own speed variation.

The measured pass is not at a constant speed: the sections average 75-78 km/h but the whole record averages
62 km/h, so the record itself contains slower stretches.  That is exactly the lever the FDD result needed:

* a **vehicle** mode keeps its frequency whatever the speed;
* a **track** periodicity keeps its *wavelength* (sleeper spacing, corrugation pitch), so its frequency
  scales with the speed.

For each speed bin this script decomposes the spectrum, collects peaks, and then classifies every peak that
repeats across bins as ``frequency-locked`` (vehicle) or ``wavelength-locked`` (track) by fitting
``f = a + b v`` and comparing ``b`` with ``f / v``.

Run:  python -X utf8 scripts/s23_speed_separation.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

WORK = Path(r"F:\velch_tmp\fdd")
SAMPLE_RATE_HZ = 4000.0
SEGMENT_SECONDS = 2.0
BAND_HZ = (5.0, 200.0)
PROMINENCE_DB = 6.0
BIN_EDGES_KMH = (30.0, 45.0, 55.0, 65.0, 75.0, 90.0)
MATCH_TOLERANCE = 0.03
SLEEPER_SPACING_M = 0.6


def load(path: Path) -> dict:
    from scipy.io import loadmat

    data = loadmat(str(path), squeeze_me=True, variable_names=["Vi_y", "Vi_Speed", "Vi_pks"])
    vertical = np.asarray(data["Vi_y"], dtype=float)
    speed_kmh = np.asarray(data["Vi_Speed"], dtype=float).ravel()
    if speed_kmh.size != vertical.shape[0]:
        raise SystemExit(f"speed has {speed_kmh.size} samples but the channels have {vertical.shape[0]}")
    return {"vertical": vertical, "speed_kmh": speed_kmh,
            "mileage_m": np.asarray(data["Vi_pks"], dtype=float).ravel() * 1000.0}


def prepare(values: np.ndarray) -> np.ndarray:
    from scipy.signal import butter, detrend, sosfiltfilt

    block = detrend(np.asarray(values, dtype=float), axis=0, type="linear")
    sos = butter(4, [BAND_HZ[0] / (SAMPLE_RATE_HZ / 2.0), BAND_HZ[1] / (SAMPLE_RATE_HZ / 2.0)],
                 btype="band", output="sos")
    return sosfiltfilt(sos, block, axis=0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", default=r"F:\ai道岔状态反演辨识\75kmh数据\Run_75kmh_E1toE2.mat")
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    from velch.inverse.spectral import find_peaks, spectral_matrix

    record = load(Path(args.record))
    speed = record["speed_kmh"]
    print(f"record {Path(args.record).name}: {speed.size} samples, "
          f"speed {speed.min():.1f}-{speed.max():.1f} km/h, mean {speed.mean():.1f} km/h")
    histogram, edges = np.histogram(speed, bins=np.arange(0.0, 100.0, 5.0))
    print("speed histogram (km/h: seconds):")
    for count, edge in zip(histogram, edges[:-1]):
        if count:
            print(f"  {edge:5.1f}-{edge + 5.0:5.1f}: {count / SAMPLE_RATE_HZ:6.1f} s")

    bins: list[tuple[float, float, np.ndarray, float]] = []
    for low, high in zip(BIN_EDGES_KMH[:-1], BIN_EDGES_KMH[1:]):
        mask = (speed >= low) & (speed < high)
        samples = int(np.count_nonzero(mask))
        if samples < int(2.5 * SAMPLE_RATE_HZ):
            print(f"  bin {low:.0f}-{high:.0f} km/h: skipped ({samples} samples)")
            continue
        spread = float(speed[mask].std())
        if spread > 2.0:
            # A speed ramp is not a speed bin: the trajectory is accelerating, so the excitation is
            # non-stationary inside the segment and no peak position is attributable to a speed.
            print(f"  bin {low:.0f}-{high:.0f} km/h: rejected as a ramp "
                  f"(speed std {spread:.2f} km/h > 2.0)")
            continue
        bins.append((low, high, prepare(record["vertical"][mask]), float(speed[mask].mean())))
    if len(bins) < 2:
        raise SystemExit(f"only {len(bins)} speed bin(s) carry enough signal; two are needed to separate "
                         "vehicle modes from track periodicity")

    payload = {"record": Path(args.record).name, "bins": [], "classification": []}
    per_bin: list[tuple[float, list[float]]] = []
    for low, high, signal, mean_speed in bins:
        decomposition = spectral_matrix(signal, sample_rate_hz=SAMPLE_RATE_HZ,
                                      segment_seconds=SEGMENT_SECONDS, band=BAND_HZ)
        peaks = find_peaks(decomposition, prominence_db=PROMINENCE_DB)
        frequencies = [peak.frequency_hz for peak in peaks]
        per_bin.append((mean_speed, frequencies))
        print(f"\nbin {low:.0f}-{high:.0f} km/h (mean {mean_speed:.1f}, "
              f"{signal.shape[0] / SAMPLE_RATE_HZ:.1f} s, resolution {decomposition.resolution_hz:.3f} Hz): "
              f"{len(frequencies)} peak(s)")
        print("  " + ", ".join(f"{value:.1f}" for value in frequencies))
        payload["bins"].append({"low_kmh": low, "high_kmh": high, "mean_kmh": mean_speed,
                               "peaks_hz": frequencies,
                               "resolution_hz": decomposition.resolution_hz})

    # Classify each frequency that appears in at least two bins.
    candidates = sorted({value for _, values in per_bin for value in values})
    speeds = np.array([speed for speed, _ in per_bin])
    print(f"\nclassification over {len(per_bin)} speed bins "
          f"({', '.join(f'{value:.0f}' for value in speeds)} km/h)")
    for candidate in candidates:
        hits = []
        for speed_value, values in per_bin:
            array = np.asarray(values)
            if array.size == 0:
                continue
            nearest = float(array[np.argmin(np.abs(array - candidate))])
            if abs(nearest - candidate) / candidate <= MATCH_TOLERANCE:
                hits.append((speed_value, nearest))
        if len(hits) < 2:
            continue
        observed = np.array([value for _, value in hits])
        used = np.array([speed for speed, _ in hits])
        slope, intercept = np.polyfit(used, observed, 1) if len(hits) >= 2 else (0.0, float(candidate))
        # A wavelength-locked peak has f = v / lambda, i.e. slope ~ candidate / v and intercept ~ 0.
        # A wavelength-locked peak has f = v/lambda, so its slope is exactly f/v = order_slope.  A
        # frequency-locked one has slope 0.  Anything in between is undecided, and the previous version of
        # this line multiplied the threshold by the mean speed (0.15 * 0.9 * 65 = 8.8 Hz per km/h), which
        # called every peak frequency-locked by construction.
        order_slope = float(np.mean(observed / used))
        relative_slope = float(slope / max(order_slope, 1e-12))
        vehicle = abs(slope) < 0.3 * order_slope
        wavelength_m = float(np.mean(used / 3.6) / candidate)
        kind = "frequency-locked (vehicle)" if vehicle else "wavelength-locked (track)"
        print(f"  {candidate:7.2f} Hz: {len(hits)} bin(s)  slope {slope:+.3f} Hz per km/h, "
              f"order slope {order_slope:6.3f}  -> {kind}")
        payload["classification"].append({
            "frequency_hz": candidate, "bins": len(hits), "slope_hz_per_kmh": slope,
            "intercept_hz": intercept, "kind": "vehicle" if vehicle else "track",
            "equivalent_wavelength_m": wavelength_m,
            "equivalent_order_ratio": relative_slope,
        })

    vehicles = [row for row in payload["classification"] if row["kind"] == "vehicle"]
    tracks = [row for row in payload["classification"] if row["kind"] == "track"]
    print(f"\nVERDICT: {len(vehicles)} frequency-locked, {len(tracks)} wavelength-locked")
    for row in vehicles:
        print(f"  vehicle candidate: {row['frequency_hz']:.2f} Hz "
              f"(slope {row['slope_hz_per_kmh']:+.3f} Hz per km/h)")
    target = Path(args.json) if args.json else WORK / "speed_separation.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"written {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
