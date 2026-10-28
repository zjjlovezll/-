"""Frequency-resolved inversion: is the band limit a scalar problem or a spectrum problem?

Round 193 inverted a random band-limited record with one gain per band and got 3 of 8 bands inside
2 dB, in a regime where the contact law was demonstrably linear (mean penetration 63-65.5 um against
65.47 um static).  The diagnosis there was that the transfer varies **inside** a one-third-octave
band -- round 192's single-tone calibration rises 29 % between 85.2 and 94.2 Hz -- so one scalar
cannot represent it.

This script tests that diagnosis directly, with the same pre-registered bands, the same seeds and the
same criterion, changing only the estimator:

* calibration seed 20261029, one band at a time; from it, the complex transfer
  ``H(f) = A_a(f) / A_r(f)`` per frequency bin, where ``A_r`` is the *input* record actually applied
  under the leading wheel (the raw record interpolated at the wheel's station and multiplied by the
  same half-cosine window the solver applies), so nothing about the window has to be assumed;
* bins are kept when they carry 99 % of the band's input energy in the calibration run;
* test seeds 20261030 and 20261031, all four bands together: ``r(f) = a(f)/H(f)`` bin by bin, then
  the band rms -- compared against the *same* input rms restricted to the same bins, so the number
  measures the transfer and not band truncation;
* the scalar estimator is evaluated on exactly the same runs and bins, so the comparison is paired;
* criterion unchanged: |error| <= 2 dB per band, band hit rate reported, band edges not moved.

Usage:
    PYTHONPATH=src python -X utf8 scripts/s38_spectral_bands.py
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np

from velch.irregularity import (IrregularityTrack, ShiftedSeries, scaled_track, window_factor)
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

BASE_CASE = Path("F:/velch_data/validation/crh380a_m/case_A_final_law.json")
OUT_DIR = Path("../scratch/s38")
PATCH_M = (42.5, 45.5)
STEP_M = 2.5e-3
FADE_M = 0.05
LAMBDAS_M = (0.10, 0.30)
BANDS = 4
HARMONICS = 24
RMS_UM = 8.0
CALIBRATION_SEED = 20261029
TEST_SEEDS = (20261030, 20261031)
HALF_GAUGE_M = 0.7465
X_START_M = 30.0
LEAD_AXLE_OFFSET_M = 10.0
SPEED_KMH = 70.3206
GATE_DB = 2.0
ENERGY_FRACTION = 0.99


def band_edges() -> list[tuple[float, float]]:
    edges = np.exp(np.linspace(math.log(LAMBDAS_M[0]), math.log(LAMBDAS_M[1]), BANDS + 1))
    return [(float(low), float(high)) for low, high in zip(edges[:-1], edges[1:])]


def random_band(seed: int, index: int, edges, s_m: np.ndarray) -> np.ndarray:
    rng = np.random.default_rng((seed, index))
    low, high = edges
    wavenumbers = np.sort(rng.uniform(1.0 / high, 1.0 / low, HARMONICS))
    phases = rng.uniform(0.0, 2.0 * math.pi, HARMONICS)
    signal = np.zeros_like(s_m)
    for k, phase in zip(wavenumbers, phases):
        signal += np.sin(2.0 * math.pi * k * s_m + phase)
    return signal / float(np.sqrt(np.mean(signal ** 2)))


def record(seed: int, *, band_index: int | None, edges) -> tuple[IrregularityTrack, np.ndarray]:
    start, end = PATCH_M
    count = int(round((end - start) / STEP_M)) + 1
    s_m = start + STEP_M * np.arange(count)
    vertical = np.zeros_like(s_m)
    for index, (low, high) in enumerate(edges):
        if band_index is not None and index != band_index:
            continue
        vertical += RMS_UM * 1e-6 * random_band(seed, index, (low, high), s_m)
    track = IrregularityTrack(s_m=s_m, lateral_m=np.zeros_like(s_m), vertical_m=vertical,
                             roll_rad=np.zeros_like(s_m), gauge_m=np.zeros_like(s_m),
                             source=f"random bands, seed {seed}")
    return track, vertical


def build_case(*, duration_s: float, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = json.loads(BASE_CASE.read_text(encoding="utf-8"))
    run = raw["run"]
    run["x_start_m"] = X_START_M
    run["duration_s"] = duration_s
    run["output_step_s"] = 5.0e-4
    run["max_solver_step_s"] = 5.0e-5
    run["method"] = "BDF"
    run["jacobian"] = "analytic"
    run["rtol"] = 1.0e-6
    run["atol"] = 1.0e-8
    run.pop("initial_state", None)
    raw["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    raw["id"] = f"s38_{name}"
    raw["purpose"] = "synthetic"
    target = OUT_DIR / name
    target.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return target


def shift_left_rails(case, track: IrregularityTrack):
    rails = []
    for rail in case.rails:
        if str(rail.id).endswith("left"):
            bodies = tuple(replace(body, series=ShiftedSeries(body.series, track, "left",
                                                              HALF_GAUGE_M))
                           for body in rail.bodies)
            rails.append(replace(rail, bodies=bodies))
        else:
            rails.append(rail)
    return replace(case, rails=tuple(rails))


def applied_input(vertical: np.ndarray, times: np.ndarray) -> np.ndarray:
    """The rail-height record actually seen by the leading wheel, in time.

    The station of the leading wheel is ``x_start + axle offset + v t``; the solver multiplies the
    raw record by the half-cosine window, so the same factor is applied here rather than assumed.
    """
    s_m = PATCH_M[0] + STEP_M * np.arange(vertical.size)
    speed = SPEED_KMH / 3.6
    station = X_START_M + LEAD_AXLE_OFFSET_M + speed * times
    raw = np.interp(station, s_m, vertical, left=0.0, right=0.0)
    factor = window_factor(station, start_m=PATCH_M[0], end_m=PATCH_M[1], fade_m=FADE_M)
    return raw * factor


def amplitude_spectrum(signal: np.ndarray, times: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = int(signal.size)
    taper = np.hanning(n)
    spectrum = np.fft.rfft(signal * taper)
    frequencies = np.fft.rfftfreq(n, d=float(times[1] - times[0]))
    return frequencies, (2.0 / float(taper.sum())) * spectrum


def band_mask(frequencies: np.ndarray, low: float, high: float) -> np.ndarray:
    speed = SPEED_KMH / 3.6
    return (frequencies >= speed / high) & (frequencies <= speed / low)


def energy_bins(input_amplitudes: np.ndarray, fraction: float = ENERGY_FRACTION) -> np.ndarray:
    """Indices of the bins carrying `fraction` of the input energy, in descending order."""
    power = np.abs(input_amplitudes) ** 2
    order = np.argsort(power)[::-1]
    cumulative = np.cumsum(power[order]) / max(float(power.sum()), 1e-30)
    keep = order[: int(np.searchsorted(cumulative, fraction)) + 1]
    return np.sort(keep)


def rms_of(amplitudes: np.ndarray) -> float:
    return float(np.sqrt(0.5 * float((np.abs(amplitudes) ** 2).sum())))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=0.30)
    parser.add_argument("--json", type=Path, default=OUT_DIR / "spectral.json")
    args = parser.parse_args(argv)

    speed = SPEED_KMH / 3.6
    entry_s = (PATCH_M[0] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    exit_s = (PATCH_M[1] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    edges = band_edges()
    print(f"straight route, {SPEED_KMH:.2f} km/h, frequency-resolved inversion, "
          f"window {entry_s:.4f}..{exit_s:.4f} s")
    if args.duration < exit_s:
        raise SystemExit("--duration ends before the axle leaves the patch")

    transfers: dict[int, dict] = {}
    for index, (low, high) in enumerate(edges):
        track, vertical = record(CALIBRATION_SEED, band_index=index, edges=edges)
        path = build_case(duration_s=args.duration, name=f"case_calib_{index}.json")
        case = shift_left_rails(load_vehicle_case(path),
                                scaled_track(track, channels=("vertical",), start_m=PATCH_M[0],
                                             end_m=PATCH_M[1], fade_m=FADE_M))
        result = simulate_vehicle(case)
        summary = result.summary
        if summary["result_status"] != "numerically_checked":
            raise SystemExit(f"calibration band {index} did not integrate")
        times = result.times_s
        mask = (times >= entry_s) & (times <= exit_s)
        window = times[mask]
        names = result.acceleration_names
        channel = next(n for n in names if n.startswith("axle1") and "z_acc" in n)
        acceleration = result.accelerations[mask, names.index(channel)]
        frequencies, a_spectrum = amplitude_spectrum(acceleration, window)
        _, input_spectrum = amplitude_spectrum(applied_input(vertical, window), window)
        inside = band_mask(frequencies, low, high)
        keep = energy_bins(input_spectrum[inside])
        bins = np.nonzero(inside)[0][keep]
        transfers[index] = {
            "bins": bins,
            "frequencies": frequencies[bins],
            "H": a_spectrum[bins] / input_spectrum[bins],
            "input_rms": rms_of(input_spectrum[bins]),
            "output_rms": rms_of(a_spectrum[bins]),
        }
        print(f"  calibration band {index} ({low:.4f}-{high:.4f} m): "
              f"{summary['result_status']}, {bins.size} of {int(inside.sum())} bins kept, "
              f"input rms {transfers[index]['input_rms'] * 1e6:6.3f} um, "
              f"output rms {transfers[index]['output_rms']:8.4f} m/s2")

    report = {"route": "straight", "speed_kmh": SPEED_KMH, "rms_um": RMS_UM,
              "calibration_seed": CALIBRATION_SEED, "test_seeds": list(TEST_SEEDS),
              "gate_db": GATE_DB, "energy_fraction": ENERGY_FRACTION, "tests": []}
    spectral_hits = scalar_hits = predictions = 0
    for seed in TEST_SEEDS:
        track, vertical = record(seed, band_index=None, edges=edges)
        path = build_case(duration_s=args.duration, name=f"case_test_{seed}.json")
        case = shift_left_rails(load_vehicle_case(path),
                                scaled_track(track, channels=("vertical",), start_m=PATCH_M[0],
                                             end_m=PATCH_M[1], fade_m=FADE_M))
        result = simulate_vehicle(case)
        summary = result.summary
        if summary["result_status"] != "numerically_checked":
            raise SystemExit(f"test seed {seed} did not integrate")
        times = result.times_s
        mask = (times >= entry_s) & (times <= exit_s)
        window = times[mask]
        names = result.acceleration_names
        channel = next(n for n in names if n.startswith("axle1") and "z_acc" in n)
        acceleration = result.accelerations[mask, names.index(channel)]
        frequencies, a_spectrum = amplitude_spectrum(acceleration, window)
        _, input_spectrum = amplitude_spectrum(applied_input(vertical, window), window)
        print(f"\n  test seed {seed}: {summary['result_status']}, mean penetration "
              f"{np.mean([result.contacts[i]['axle1_left'].geometry.penetration_m for i in np.nonzero(mask)[0] if result.contacts[i].get('axle1_left') is not None and result.contacts[i]['axle1_left'].geometry is not None]) * 1e6:.2f} um")
        entry = {"seed": seed, "bands": []}
        for index, (low, high) in enumerate(edges):
            transfer = transfers[index]
            bins = transfer["bins"]
            truth = rms_of(input_spectrum[bins])
            recovered = rms_of(a_spectrum[bins] / transfer["H"])
            # paired scalar estimator on exactly the same bins
            gain = transfer["output_rms"] / transfer["input_rms"]
            recovered_scalar = rms_of(a_spectrum[bins]) / gain
            db = 20.0 * math.log10(recovered / truth)
            db_scalar = 20.0 * math.log10(recovered_scalar / truth)
            spectral_ok = abs(db) <= GATE_DB
            scalar_ok = abs(db_scalar) <= GATE_DB
            spectral_hits += int(spectral_ok)
            scalar_hits += int(scalar_ok)
            predictions += 1
            entry["bands"].append({"band": f"{low:.4f}-{high:.4f}", "bins": int(bins.size),
                                   "truth_um": truth * 1e6, "recovered_um": recovered * 1e6,
                                   "error_db": db, "within_gate": bool(spectral_ok),
                                   "scalar_recovered_um": recovered_scalar * 1e6,
                                   "scalar_error_db": db_scalar,
                                   "scalar_within_gate": bool(scalar_ok)})
            print(f"    {low:.4f}-{high:.4f} m  truth {truth * 1e6:6.2f} um | "
                  f"spectral {recovered * 1e6:6.2f} ({db:+6.2f} dB) "
                  f"{'PASS' if spectral_ok else 'FAIL'} | scalar "
                  f"{recovered_scalar * 1e6:6.2f} ({db_scalar:+6.2f} dB) "
                  f"{'PASS' if scalar_ok else 'FAIL'}")
        report["tests"].append(entry)

    report["spectral_hits"] = spectral_hits
    report["scalar_hits"] = scalar_hits
    report["predictions"] = predictions
    report["verdict"] = "pass" if spectral_hits == predictions else "degraded"
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n  band hit rate: spectral {spectral_hits}/{predictions}, "
          f"scalar {scalar_hits}/{predictions} on the same bins -> {report['verdict'].upper()}")
    print(f"  wrote {args.json}")
    return 0 if spectral_hits == predictions else 1


if __name__ == "__main__":
    raise SystemExit(main())
