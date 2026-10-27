"""Find the corrugated sections in a measured run and score them against the published truth.

The dataset (``Run_75kmh_E1toE2.mat``) is an onboard recording of a commercial metro run:
two vertical axle-box accelerations at 4 kHz, an interior microphone at 48 kHz, a Doppler
speed signal and the kilometric position integrated from it.  The paper that ships with it
(Soto-Ocampo et al., Mathematics 2025, 13, 2815) lists six sections confirmed as corrugated:

    S1 4.243-4.300 km   S2 4.718-4.805 km   S3 4.855-4.927 km
    S4 5.250-5.352 km   S5 5.438-5.577 km   S6 5.729-5.829 km

Their method is acoustic and it is a *detector*: the deliverable is "these sections are
corrugated", not "the rail surface is X micrometres".  There is no measured irregularity
profile in the dataset, so an amplitude inversion cannot be scored here; what can be scored
is localisation.  This script asks the same question of both channels, so the vibration
channel can be compared with the acoustic one on equal terms.

Per spatial window (25 m long, 5 m apart, so a 40-140 m section is covered by several
overlapping estimates):

    index_db = peak PSD above the median PSD inside a band that the local speed maps to a
               fixed *wavelength* range (20-350 mm).  The band is derived from speed, not
               hard-coded, so 40 km/h and 75 km/h ask about the same wavelengths -- the
               property the paper's own indices are built on.

Scoring is fixed before the run and reported three ways:

    AUC        probability that a random window inside a section ranks above a random
               window outside -- scale free, no threshold to tune.
    hits       a section is detected when its peak index beats the 95th percentile of the
               windows outside every section (5 % *per-section* false-alarm rate, calibrated on pseudo-sections of the same length).
    error_m    distance from that peak to the nearest edge of the section.

Usage::

    python -X utf8 scripts/s10_measured_corrugation.py
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

WINDOW_M = 25.0
HOP_M = 5.0
# The paper's Table 4 puts every one of the six sections at 24-31 mm of wavelength
# (692-844 Hz at 75 km/h).  A wide band was tried first and buried that line in the
# neighbouring content, so the band is the measured one, converted per local speed.
SHORTEST_M = 0.018
LONGEST_M = 0.040
FALSE_ALARM_PERCENT = 95.0
SEARCH_M = 40.0
SEGMENT = 1024

SECTIONS = (
    ("S1", 4.243e3, 4.300e3),
    ("S2", 4.718e3, 4.805e3),
    ("S3", 4.855e3, 4.927e3),
    ("S4", 5.250e3, 5.352e3),
    ("S5", 5.438e3, 5.577e3),
    ("S6", 5.729e3, 5.829e3),
)


@dataclass(frozen=True)
class Window:
    position_m: float
    speed_m_s: float
    index_db: float
    peak_hz: float
    rms: float


def load(path: Path) -> dict:
    """Read the .mat file without assuming the MATLAB version."""
    import scipy.io

    raw = scipy.io.loadmat(str(path))
    vertical = np.asarray(raw["Vi_y"], dtype=float)
    if vertical.ndim != 2 or vertical.shape[1] != 2:
        raise SystemExit(f"Vi_y should be two accelerometer columns, got {vertical.shape}")
    return {
        "vertical": vertical,
        "speed": np.asarray(raw["Vi_Speed"], dtype=float).ravel(),
        # Vi_pks is already in kilometres (3.798 -> 6.303); metres are what the sections use
        "pks": np.asarray(raw["Vi_pks"], dtype=float).ravel() * 1000.0,
        "time": np.asarray(raw["Vi_t"], dtype=float).ravel(),
        "sound": np.asarray(raw["So_y"], dtype=float).ravel(),
        "sound_pks": np.asarray(raw["So_pks"], dtype=float).ravel() * 1000.0,
        "sound_time": np.asarray(raw["So_t"], dtype=float).ravel(),
    }


def sampling_interval(time: np.ndarray) -> float:
    return float(np.median(np.diff(time)))


def band_for_speed(speed_m_s: float, rate_hz: float) -> tuple[float, float]:
    """Wavelength range -> frequency range at this speed, clamped to what the record carries."""
    low = speed_m_s / LONGEST_M
    high = speed_m_s / SHORTEST_M
    return max(low, 1.0), min(high, 0.45 * rate_hz)


def prominence(segment: np.ndarray, rate_hz: float, speed_m_s: float) -> tuple[float, float]:
    """Welch peak-to-median ratio in dB, plus the frequency of that peak, inside the band."""
    low, high = band_for_speed(speed_m_s, rate_hz)
    length = min(SEGMENT, len(segment))
    if length < 64:
        return 0.0, 0.0
    window = np.hanning(length)
    step = max(length // 2, 1)
    density = np.zeros(length // 2 + 1)
    count = 0
    for start in range(0, len(segment) - length + 1, step):
        spectrum = np.fft.rfft(segment[start : start + length] * window)
        density += np.abs(spectrum) ** 2
        count += 1
    if count == 0:
        return 0.0, 0.0
    density /= count
    frequencies = np.fft.rfftfreq(length, d=1.0 / rate_hz)
    band = (frequencies >= low) & (frequencies <= high)
    if not np.any(band):
        return 0.0, 0.0
    values = density[band]
    peak_index = int(np.argmax(values))
    floor = float(np.median(values))
    if floor <= 0.0:
        return 0.0, float(frequencies[band][peak_index])
    ratio = 10.0 * math.log10(max(float(values[peak_index]) / floor, 1e-12))
    return ratio, float(frequencies[band][peak_index])


def analyse(data: dict, channel: str, window_m: float = WINDOW_M, hop_m: float = HOP_M) -> list[Window]:
    if channel == "vibration":
        signals = data["vertical"]
        position = data["pks"]
        rate = 1.0 / sampling_interval(data["time"])
        order = np.argsort(position)
        speed = data["speed"][order] / 3.6  # km/h -> m/s
    elif channel == "sound":
        signals = data["sound"].reshape(-1, 1)
        position = data["sound_pks"]
        rate = 1.0 / sampling_interval(data["sound_time"])
        order = np.argsort(position)
        # the sound shares the run: interpolate the vibration speed onto sound positions
        source = np.argsort(data["pks"])
        speed = np.interp(
            position[order], data["pks"][source], data["speed"][source] / 3.6
        )
    else:
        raise ValueError(channel)

    position = position[order]
    signals = signals[order]

    start = float(position[0])
    stop = float(position[-1]) - window_m
    results: list[Window] = []
    for centre in np.arange(start + 0.5 * window_m, stop, hop_m):
        lo = int(np.searchsorted(position, centre - 0.5 * window_m))
        hi = int(np.searchsorted(position, centre + 0.5 * window_m))
        if hi - lo < SEGMENT:
            continue
        local_speed = float(np.median(speed[lo:hi]))
        if local_speed <= 3.0:
            continue
        best_ratio = -1e9
        best_peak = 0.0
        scale = 0.0
        for column in range(signals.shape[1]):
            segment = signals[lo:hi, column]
            scale = max(scale, float(np.std(segment)))
            ratio, peak = prominence(segment, rate, local_speed)
            if ratio > best_ratio:
                best_ratio, best_peak = ratio, peak
        results.append(
            Window(
                position_m=float(centre),
                speed_m_s=local_speed,
                index_db=float(best_ratio),
                peak_hz=float(best_peak),
                rms=scale,
            )
        )
    return results


def auc(inside: np.ndarray, outside: np.ndarray) -> float:
    """Probability that a random inside value exceeds a random outside value."""
    if inside.size == 0 or outside.size == 0:
        return float("nan")
    combined = np.concatenate([inside, outside])
    order = np.argsort(combined, kind="mergesort")
    ranks = np.empty(combined.size)
    ranks[order] = np.arange(1, combined.size + 1)
    for value in np.unique(combined):
        mask = combined == value
        if mask.sum() > 1:
            ranks[mask] = ranks[mask].mean()
    total = ranks[: inside.size].sum() - inside.size * (inside.size + 1) / 2.0
    return float(total / (inside.size * outside.size))


def _pseudo_segment_maxima(
    positions: np.ndarray, indices: np.ndarray, hop: float
) -> np.ndarray:
    """Max over pseudo-sections of the real lengths, placed only outside the real ones.

    This is what makes the false-alarm rate a *segment* rate: a section is declared
    detected when its peak beats the 95th percentile of what an equally long stretch of
    ordinary track produces.  Using the single-window percentile here (the first version)
    understated the effective rate by 1 - 0.95**n, i.e. 46-76 %.
    """
    lengths = np.array([stop - start for _name, start, stop in SECTIONS])
    maxima = []
    low = float(positions.min())
    high = float(positions.max())
    for length in lengths:
        for begin in np.arange(low, high - length, hop):
            stop = begin + length
            if any(begin < edge_stop and stop > edge_start for _n, edge_start, edge_stop in SECTIONS):
                continue
            mask = (positions >= begin) & (positions <= stop)
            if np.count_nonzero(mask) < 3:
                continue
            maxima.append(float(np.max(indices[mask])))
    return np.array(maxima)


def _local_maxima(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Indices of interior local maxima, so a peak is a feature rather than a threshold artefact."""
    mask = np.zeros(len(indices), dtype=bool)
    if len(indices) >= 3:
        mask[1:-1] = (indices[1:-1] > indices[:-2]) & (indices[1:-1] >= indices[2:])
    return np.flatnonzero(mask)


def _binomial_tail(hits: int, trials: int, probability: float) -> float:
    """P(X >= hits) under the null that every section is empty."""
    if hits <= 0:
        return 1.0
    total = 0.0
    for k in range(hits, trials + 1):
        total += math.comb(trials, k) * probability**k * (1.0 - probability) ** (trials - k)
    return min(total, 1.0)


def score(results: list[Window], label: str, *, hop_m: float = HOP_M,
          search_m: float = SEARCH_M) -> dict:
    positions = np.array([item.position_m for item in results])
    indices = np.array([item.index_db for item in results])
    inside = np.zeros(len(results), dtype=bool)
    for _name, start, stop in SECTIONS:
        inside |= (positions >= start) & (positions <= stop)
    if not np.any(inside) or np.all(inside):
        raise SystemExit("no usable windows inside or outside the sections")

    pseudo = _pseudo_segment_maxima(positions, indices, hop_m)
    if pseudo.size < 10:
        raise SystemExit(f"only {pseudo.size} pseudo-sections: too short a record to calibrate")
    threshold = float(np.percentile(pseudo, FALSE_ALARM_PERCENT))
    far = 1.0 - FALSE_ALARM_PERCENT / 100.0

    peaks = _local_maxima(positions, indices)
    peaks = peaks[indices[peaks] > threshold]
    peak_positions = positions[peaks]
    peak_values = indices[peaks]
    used = np.zeros(len(peaks), dtype=bool)

    rows = []
    detected = 0
    for name, start, stop in SECTIONS:
        mask = (positions >= start) & (positions <= stop)
        if not np.any(mask):
            rows.append({"section": name, "peak_db": None, "mean_db": None, "peak_km": None,
                         "localisation_error_m": None, "detected": False})
            continue
        local = indices[mask]
        # a section is detected when a free standing peak lands on it or close to it;
        # the error is measured from that peak, so it can be positive (and can be a miss)
        candidates = np.flatnonzero(
            (~used) & (peak_positions >= start - search_m) & (peak_positions <= stop + search_m)
        )
        hit = False
        peak_m = float("nan")
        error = None
        if candidates.size:
            best = candidates[int(np.argmax(peak_values[candidates]))]
            used[best] = True
            peak_m = float(peak_positions[best])
            error = 0.0 if start <= peak_m <= stop else min(abs(peak_m - start), abs(peak_m - stop))
            hit = True
        detected += int(hit)
        rows.append({
            "section": name,
            "start_km": start / 1e3,
            "stop_km": stop / 1e3,
            "inside_max_db": float(np.max(local)),
            "mean_db": float(np.mean(local)),
            "peak_km": peak_m / 1e3 if hit else None,
            "localisation_error_m": error,
            "detected": bool(hit),
        })

    return {
        "channel": label,
        "windows": len(results),
        "inside_windows": int(inside.sum()),
        "pseudo_sections": int(pseudo.size),
        "threshold_db": threshold,
        "false_alarm_rate_per_section": far,
        "inside_median_db": float(np.median(indices[inside])),
        "outside_median_db": float(np.median(indices[~inside])),
        "inside_minus_outside_db": float(np.median(indices[inside]) - np.median(indices[~inside])),
        "auc": auc(indices[inside], indices[~inside]),
        "sections_detected": detected,
        "sections_total": len(SECTIONS),
        "detection_rate": detected / len(SECTIONS),
        "expected_hits_if_empty": len(SECTIONS) * far,
        "null_probability": _binomial_tail(detected, len(SECTIONS), far),
        "unassigned_peaks": int(np.count_nonzero(~used)),
        "rows": rows,
    }


def report(summary: dict) -> None:
    print(f"\n=== {summary['channel']}: {summary['windows']} windows, "
          f"{summary['inside_windows']} inside the six sections")
    print(f"threshold   {summary['threshold_db']:.2f} dB "
          f"(95th percentile of {summary['pseudo_sections']} pseudo-sections)")
    print(f"medians     inside {summary['inside_median_db']:.2f} dB, "
          f"outside {summary['outside_median_db']:.2f} dB "
          f"(+{summary['inside_minus_outside_db']:.2f})")
    print(f"AUC         {summary['auc']:.3f}")
    print(f"{'sec':4} {'km range':16} {'max dB':>8} {'mean dB':>8} {'peak km':>8} "
          f"{'err m':>7} {'hit':>4}")
    for row in summary["rows"]:
        if row["inside_max_db"] is None:
            print(f"{row['section']:4} {'-':16} {'-':>8} {'-':>8} {'-':>8} {'-':>7}    no")
            continue
        peak_km = "-" if row["peak_km"] is None else f"{row['peak_km']:.3f}"
        error = "-" if row["localisation_error_m"] is None else f"{row['localisation_error_m']:.1f}"
        print(f"{row['section']:4} {row['start_km']:.3f}-{row['stop_km']:.3f} "
              f"{row['inside_max_db']:8.2f} {row['mean_db']:8.2f} {peak_km:>8} "
              f"{error:>7} {'yes' if row['detected'] else 'no':>4}")
    print(f"detection   {summary['sections_detected']}/{summary['sections_total']} "
          f"({100 * summary['detection_rate']:.0f} %) at a "
          f"{100 * summary['false_alarm_rate_per_section']:.0f} % per-section false-alarm rate")
    print(f"null        {summary['expected_hits_if_empty']:.2f} expected hits if every section "
          f"were empty, P(X >= {summary['sections_detected']}) = {summary['null_probability']:.3f}; "
          f"{summary['unassigned_peaks']} unassigned peaks above threshold")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(r"F:\ai道岔状态反演辨识\75kmh数据\Run_75kmh_E1toE2.mat"),
    )
    parser.add_argument("--json", type=Path, default=Path(r"F:\velch_tmp\s10\detection.json"))
    options = parser.parse_args()

    data = load(options.data)
    print(f"file        {options.data.name}")
    print(f"amplitude   vibration rms {np.sqrt(np.mean(data['vertical'] ** 2)):.2f}, "
          f"sound rms {np.sqrt(np.mean(data['sound'] ** 2)):.3f}")
    print(f"position    {data['pks'].min() / 1e3:.3f} - {data['pks'].max() / 1e3:.3f} km, "
          f"vibration at {1.0 / sampling_interval(data['time']):.0f} Hz, "
          f"sound at {1.0 / sampling_interval(data['sound_time']):.0f} Hz")

    payload = {}
    for channel in ("vibration", "sound"):
        results = analyse(data, channel)
        summary = score(results, channel)
        report(summary)
        payload[channel] = {"summary": summary, "windows": [asdict(item) for item in results]}

    options.json.parent.mkdir(parents=True, exist_ok=True)
    options.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwritten     {options.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
