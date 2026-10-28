"""Route A: calibrate the transfer with pure tones at each frequency bin, then invert again.

Round 194 inverted a random band-limited record bin by bin and got 6 of 8 bands inside 2 dB -- exactly
the scalar estimator's score on the same bins -- and the two estimators failed *together* on one band
(+2.17 dB spectral against +2.37 dB scalar).  That pattern says the shortfall is shared, not
estimator-specific.  Two candidates were left standing:

1. the transfer ``H(f)`` was estimated by H1 from a **single random realisation**, so bins where the
   input carries little energy give a noisy ``H``;
2. the residual is intrinsic -- realisations differ, or the bands interact.

Route A removes candidate 1 by construction: ``H`` is measured with a **pure tone at each kept bin**,
where the input is deterministic and the estimate carries no realisation noise.  Everything else --
bands, seeds, patch, channel, window, per-bin bin set, 2 dB criterion -- is unchanged, and the test
record's own band rms is the truth, so the comparison is against round 194's numbers and not against
a different question.

The criterion was fixed before running: **at least 7 of 8 predictions inside 2 dB, and the sign of a
band's offset no longer flips between the two test seeds.**

Usage:
    PYTHONPATH=src python -X utf8 scripts/s39_tone_calibrated.py
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np

from velch.irregularity import IrregularityTrack, ShiftedSeries, scaled_track, window_factor
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

BASE_CASE = Path("F:/velch_data/validation/crh380a_m/case_A_final_law.json")
OUT_DIR = Path("../scratch/s39")
PATCH_M = (42.5, 45.5)
STEP_M = 2.5e-3
FADE_M = 0.05
LAMBDAS_M = (0.10, 0.30)
BANDS = 4
HARMONICS = 24
RMS_UM = 8.0
TONE_UM = 2.5
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


def station_grid() -> np.ndarray:
    start, end = PATCH_M
    count = int(round((end - start) / STEP_M)) + 1
    return start + STEP_M * np.arange(count)


def record(seed: int, *, band_index: int | None, edges) -> tuple[IrregularityTrack, np.ndarray]:
    s_m = station_grid()
    vertical = np.zeros_like(s_m)
    for index, (low, high) in enumerate(edges):
        if band_index is not None and index != band_index:
            continue
        vertical += RMS_UM * 1e-6 * random_band(seed, index, (low, high), s_m)
    track = IrregularityTrack(s_m=s_m, lateral_m=np.zeros_like(s_m), vertical_m=vertical,
                             roll_rad=np.zeros_like(s_m), gauge_m=np.zeros_like(s_m),
                             source=f"random bands, seed {seed}")
    return track, vertical


def tone(wavenumber: float, peak_um: float = TONE_UM) -> tuple[IrregularityTrack, np.ndarray]:
    """A single pure tone across the patch, at the requested spatial frequency."""
    s_m = station_grid()
    vertical = peak_um * 1e-6 * np.sin(2.0 * math.pi * wavenumber * s_m)
    track = IrregularityTrack(s_m=s_m, lateral_m=np.zeros_like(s_m), vertical_m=vertical,
                             roll_rad=np.zeros_like(s_m), gauge_m=np.zeros_like(s_m),
                             source=f"pure tone, k {wavenumber:.4f} 1/m, {peak_um:.1f} um")
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
    raw["id"] = f"s39_{name}"
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
    power = np.abs(input_amplitudes) ** 2
    order = np.argsort(power)[::-1]
    cumulative = np.cumsum(power[order]) / max(float(power.sum()), 1e-30)
    keep = order[: int(np.searchsorted(cumulative, fraction)) + 1]
    return np.sort(keep)


def rms_of(amplitudes: np.ndarray) -> float:
    return float(np.sqrt(0.5 * float((np.abs(amplitudes) ** 2).sum())))


def accel_channel(result) -> tuple[str, np.ndarray]:
    names = result.acceleration_names
    channel = next(n for n in names if n.startswith("axle1") and "z_acc" in n)
    return channel, result.accelerations[:, names.index(channel)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=0.29)
    parser.add_argument("--json", type=Path, default=OUT_DIR / "tone.json")
    args = parser.parse_args(argv)

    speed = SPEED_KMH / 3.6
    entry_s = (PATCH_M[0] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    exit_s = (PATCH_M[1] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    edges = band_edges()
    print(f"straight route, {SPEED_KMH:.2f} km/h, tone-calibrated transfer, "
          f"window {entry_s:.4f}..{exit_s:.4f} s")
    if args.duration < exit_s:
        raise SystemExit("--duration ends before the axle leaves the patch")

    def run(track: IrregularityTrack, vertical: np.ndarray, name: str):
        path = build_case(duration_s=args.duration, name=f"case_{name}.json")
        case = shift_left_rails(load_vehicle_case(path),
                                scaled_track(track, channels=("vertical",), start_m=PATCH_M[0],
                                             end_m=PATCH_M[1], fade_m=FADE_M))
        result = simulate_vehicle(case)
        if result.summary["result_status"] != "numerically_checked":
            raise SystemExit(f"{name} did not integrate")
        times = result.times_s
        mask = (times >= entry_s) & (times <= exit_s)
        window = times[mask]
        _, acceleration = accel_channel(result)
        frequencies, a_spectrum = amplitude_spectrum(acceleration[mask], window)
        _, input_spectrum = amplitude_spectrum(applied_input(vertical, window), window)
        return result, frequencies, a_spectrum, input_spectrum, np.nonzero(mask)[0]

    # 1. the same bins round 194 used, from the same calibration realisation
    bins_by_band: dict[int, np.ndarray] = {}
    frequencies_by_band: dict[int, np.ndarray] = {}
    record_h: dict[int, np.ndarray] = {}
    for index, (low, high) in enumerate(edges):
        track, vertical = record(CALIBRATION_SEED, band_index=index, edges=edges)
        result, frequencies, a_spectrum, input_spectrum, _ = run(
            track, vertical, f"calib_{index}")
        inside = band_mask(frequencies, low, high)
        keep = energy_bins(input_spectrum[inside])
        bins_by_band[index] = np.nonzero(inside)[0][keep]
        frequencies_by_band[index] = frequencies
        record_h[index] = a_spectrum[bins_by_band[index]] / input_spectrum[bins_by_band[index]]
        print(f"  band {index} ({low:.4f}-{high:.4f} m): {bins_by_band[index].size} bins, "
              f"record input rms {rms_of(input_spectrum[bins_by_band[index]]) * 1e6:.3f} um")

    # 2. one pure tone per kept bin -> a transfer with no realisation noise in it
    tone_transfers: dict[int, dict] = {}
    total_tones = int(sum(bins.size for bins in bins_by_band.values()))
    done = 0
    for index, (low, high) in enumerate(edges):
        bins = bins_by_band[index]
        bins_dtype = np.zeros(bins.size, dtype=complex)
        inputs = np.zeros(bins.size)
        for position, bin_index in enumerate(bins):
            # the frequency axis depends only on the window, which every run shares, so the axis from
            # the calibration run is the right one for the tones as well
            frequency = float(frequencies_by_band[index][bin_index])
            track_tone, vertical_tone = tone(frequency / speed)
            result, frequencies, a_spectrum, input_spectrum, _ = run(
                track_tone, vertical_tone, f"tone_{index}_{position}")
            done += 1
            bins_dtype[position] = a_spectrum[bin_index]
            inputs[position] = input_spectrum[bin_index]
            print(f"    tone {done:2d}/{total_tones} band {index} bin {position}: "
                  f"{frequency:7.2f} Hz, input {abs(input_spectrum[bin_index]) * 1e6:6.3f} um, "
                  f"output {abs(a_spectrum[bin_index]):8.4f} m/s2")
        tone_transfers[index] = {"bins": bins, "H": bins_dtype / inputs}
        ratio = np.abs(tone_transfers[index]["H"] / record_h[index])
        print(f"    band {index}: |H_tone / H_record| per bin "
              f"{np.array2string(ratio, precision=3, floatmode='fixed')}, "
              f"median {float(np.median(ratio)):.3f} "
              f"({20.0 * math.log10(float(np.median(ratio))):+.2f} dB)")

    # 3. the same two test records, inverted with the tone transfer
    report = {"route": "straight", "speed_kmh": SPEED_KMH, "rms_um": RMS_UM,
              "tone_um": TONE_UM, "calibration_seed": CALIBRATION_SEED,
              "test_seeds": list(TEST_SEEDS), "gate_db": GATE_DB, "tests": []}
    hits = predictions = 0
    signs: dict[int, list[int]] = {index: [] for index in range(len(edges))}
    for seed in TEST_SEEDS:
        track, vertical = record(seed, band_index=None, edges=edges)
        result, frequencies, a_spectrum, input_spectrum, frames = run(
            track, vertical, f"test_{seed}")
        penetration = [result.contacts[int(i)]["axle1_left"].geometry.penetration_m
                       for i in frames
                       if result.contacts[int(i)].get("axle1_left") is not None
                       and result.contacts[int(i)]["axle1_left"].geometry is not None]
        print(f"\n  test seed {seed}: mean penetration {np.mean(penetration) * 1e6:.2f} um")
        entry = {"seed": seed, "bands": []}
        for index, (low, high) in enumerate(edges):
            transfer = tone_transfers[index]
            bins = transfer["bins"]
            truth = rms_of(input_spectrum[bins])
            recovered = rms_of(a_spectrum[bins] / transfer["H"])
            db = 20.0 * math.log10(recovered / truth)
            ok = abs(db) <= GATE_DB
            hits += int(ok)
            predictions += 1
            signs[index].append(int(np.sign(db)) if abs(db) > 0.10 else 0)
            entry["bands"].append({"band": f"{low:.4f}-{high:.4f}", "bins": int(bins.size),
                                   "truth_um": truth * 1e6, "recovered_um": recovered * 1e6,
                                   "error_db": db, "within_gate": bool(ok)})
            print(f"    {low:.4f}-{high:.4f} m  truth {truth * 1e6:6.2f} um | "
                  f"tone-calibrated {recovered * 1e6:6.2f} ({db:+6.2f} dB) "
                  f"{'PASS' if ok else 'FAIL'}")
        report["tests"].append(entry)

    flips = [index for index, values in signs.items() if len(set(values)) > 1]
    report["hits"] = hits
    report["predictions"] = predictions
    report["sign_flips"] = flips
    report["verdict"] = "pass" if hits >= predictions - 1 and not flips else "degraded"

    # 4. is the tone-versus-record gap an excursion effect?  one bin, three tone amplitudes
    sweep_index, sweep_position = 1, 2
    sweep_bin = int(bins_by_band[sweep_index][sweep_position])
    sweep_frequency = float(frequencies_by_band[sweep_index][sweep_bin])
    sweep: list[dict] = []
    print(f"\n  excursion sweep at {sweep_frequency:.2f} Hz "
          f"(band {sweep_index}, bin {sweep_position}); "
          f"record |H| there {abs(record_h[sweep_index][sweep_position]):.4f} m/s2 per m")
    for peak_um in (2.5, 6.0, 12.0, 20.0):
        track_tone, vertical_tone = tone(sweep_frequency / speed, peak_um)
        result, frequencies, a_spectrum, input_spectrum, _ = run(
            track_tone, vertical_tone, f"sweep_{peak_um:g}")
        magnitude = float(abs(a_spectrum[sweep_bin] / input_spectrum[sweep_bin]))
        penetration = [result.contacts[int(i)]["axle1_left"].geometry.penetration_m
                       for i in range(len(result.times_s))
                       if result.contacts[i].get("axle1_left") is not None
                       and result.contacts[i]["axle1_left"].geometry is not None]
        sweep.append({"peak_um": peak_um, "H": magnitude,
                      "mean_penetration_um": float(np.mean(penetration)) * 1e6})
        print(f"    tone peak {peak_um:5.1f} um -> |H| {magnitude:7.4f} m/s2 per m "
              f"({20.0 * math.log10(magnitude):+6.2f} dB), "
              f"mean penetration {np.mean(penetration) * 1e6:6.2f} um")
    report["excursion_sweep"] = {"frequency_hz": sweep_frequency, "samples": sweep,
                                 "record_H": float(abs(record_h[sweep_index][sweep_position]))}

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n  tone-calibrated hit rate {hits}/{predictions}, "
          f"bands whose offset sign flips between seeds: {flips or 'none'} "
          f"-> {report['verdict'].upper()}")
    print(f"  wrote {args.json}")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
