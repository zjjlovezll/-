"""Random irregularity, band by band, with the calibration and the test on different seeds.

Gate 6's other half: not one deterministic mixture, but a *random* surface.  The design follows the
criterion round 192 measured rather than taste: a band may carry a quantitative amplitude only if
its own gain is flat, and flatness is predicted by whether the record pushes the mean contact
penetration away from the static 65.47 um.  So the record here is band-limited (0.10-0.30 m), has
random phases per harmonic (a random process, not four sines), and is set to an rms per band that
keeps the excursion modest.

Protocol, fixed before the numbers:

1. four 1/3-octave-ish bands between 0.10 and 0.30 m, edges log-spaced;
2. each band is a sum of 24 harmonics with uniform frequencies inside the band and uniform random
   phases, normalised to the requested rms -- so the *shape* is a random draw, not a sinusoid;
3. **calibration seed 20261029**: excite one band at a time at 8 um rms and measure its gain
   g_k = rms(a_k) / rms(record_k);
4. **test seeds 20261030 and 20261031**: all four bands together at the same 8 um rms each, i.e.
   the calibration never sees the test waveforms;
5. recovery: band-pass the observed acceleration into the same frequency ranges, take its rms,
   divide by g_k, compare with the true 8 um -- the criterion is |error| <= 2 dB, and the reported
   quantity is the *band hit rate*, never a single overall number;
6. the mean penetration of every run is printed: if it has left 65.47 um, the run is outside the
   regime where the criterion is expected to hold and the document must say so.

Usage:
    PYTHONPATH=src python -X utf8 scripts/s37_random_spectrum_bands.py
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np

from velch.irregularity import IrregularityTrack, ShiftedSeries, scaled_track
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

BASE_CASE = Path("F:/velch_data/validation/crh380a_m/case_A_final_law.json")
OUT_DIR = Path("../scratch/s37")
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


def band_edges() -> list[tuple[float, float]]:
    edges = np.exp(np.linspace(math.log(LAMBDAS_M[0]), math.log(LAMBDAS_M[1]), BANDS + 1))
    return [(float(low), float(high)) for low, high in zip(edges[:-1], edges[1:])]


def random_band(seed: int, index: int, edges, s_m: np.ndarray) -> np.ndarray:
    """A band-limited random process with unit rms: 24 harmonics, uniform frequencies and phases."""
    rng = np.random.default_rng((seed, index))
    low, high = edges
    # wavenumber-space edges so the band is uniform in spatial frequency
    k_low, k_high = 1.0 / high, 1.0 / low
    wavenumbers = np.sort(rng.uniform(k_low, k_high, HARMONICS))
    phases = rng.uniform(0.0, 2.0 * math.pi, HARMONICS)
    signal = np.zeros_like(s_m)
    for k, phase in zip(wavenumbers, phases):
        signal += np.sin(2.0 * math.pi * k * s_m + phase)
    return signal / float(np.sqrt(np.mean(signal ** 2)))


def record(seed: int, *, band_index: int | None, edges) -> tuple[IrregularityTrack, dict[str, float]]:
    start, end = PATCH_M
    count = int(round((end - start) / STEP_M)) + 1
    s_m = start + STEP_M * np.arange(count)
    vertical = np.zeros_like(s_m)
    truth: dict[str, float] = {}
    for index, (low, high) in enumerate(edges):
        if band_index is not None and index != band_index:
            continue
        vertical += RMS_UM * 1e-6 * random_band(seed, index, (low, high), s_m)
        truth[f"{low:.4f}-{high:.4f}"] = RMS_UM
    track = IrregularityTrack(s_m=s_m, lateral_m=np.zeros_like(s_m), vertical_m=vertical,
                             roll_rad=np.zeros_like(s_m), gauge_m=np.zeros_like(s_m),
                             source=f"random bands, seed {seed}")
    return track, truth


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
    raw["id"] = f"s37_{name}"
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


def band_rms(signal: np.ndarray, times: np.ndarray, low_lambda: float, high_lambda: float,
             speed: float) -> tuple[float, int]:
    """rms of the record inside one wavelength band.

    Hann-tapered PSD route, so the answer is independent of where the tones fall relative to the
    bins: for a tone of amplitude A the mean square must come out A^2/2 whether the tone is
    bin-aligned or not, and for broadband noise it must come out the noise's rms.  An earlier
    version of this helper was short by a factor of sqrt(n) -- harmless for a ratio of two of its
    own outputs, which is why the recovery numbers stand, but wrong for anything printed.
    """
    n = signal.size
    taper = np.hanning(n)
    spectrum = np.fft.rfft(signal * taper)
    frequencies = np.fft.rfftfreq(n, d=float(times[1] - times[0]))
    f_low, f_high = speed / high_lambda, speed / low_lambda
    mask = (frequencies >= f_low) & (frequencies <= f_high)
    mean_square = 2.0 * (np.abs(spectrum[mask]) ** 2).sum() / (n * n * float(np.mean(taper ** 2)))
    return float(np.sqrt(mean_square)), int(mask.sum())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=0.30)
    parser.add_argument("--json", type=Path, default=OUT_DIR / "bands.json")
    args = parser.parse_args(argv)

    speed = SPEED_KMH / 3.6
    entry_s = (PATCH_M[0] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    exit_s = (PATCH_M[1] - (X_START_M + LEAD_AXLE_OFFSET_M)) / speed
    edges = band_edges()
    print(f"straight route, {SPEED_KMH:.2f} km/h, random band-limited record, {RMS_UM} um rms per "
          f"band, window {entry_s:.4f}..{exit_s:.4f} s")
    for low, high in edges:
        print(f"  band {low:.4f}-{high:.4f} m  ->  {speed / high:6.1f} .. {speed / low:6.1f} Hz")
    if args.duration < exit_s:
        raise SystemExit("--duration ends before the axle leaves the patch")

    names_channel = None
    gains = {}
    for index, (low, high) in enumerate(edges):
        track, _ = record(CALIBRATION_SEED, band_index=index, edges=edges)
        path = build_case(duration_s=args.duration, name=f"case_calib_band{index}.json")
        case = shift_left_rails(load_vehicle_case(path),
                                scaled_track(track, channels=("vertical",), start_m=PATCH_M[0],
                                             end_m=PATCH_M[1], fade_m=FADE_M))
        result = simulate_vehicle(case)
        summary = result.summary
        if summary["result_status"] != "numerically_checked":
            raise SystemExit(f"calibration band {index} did not integrate: "
                             f"{[g for g, ok in summary['gates'].items() if not ok]}")
        names = result.acceleration_names
        channel = next(n for n in names if n.startswith("axle1") and "z_acc" in n)
        names_channel = channel
        times = result.times_s
        mask = (times >= entry_s) & (times <= exit_s)
        window = times[mask]
        signal = result.accelerations[mask, names.index(channel)]
        penetrations = [result.contacts[i]["axle1_left"].geometry.penetration_m
                        for i in np.nonzero(mask)[0]
                        if result.contacts[i].get("axle1_left") is not None
                        and result.contacts[i]["axle1_left"].geometry is not None]
        observed, bins = band_rms(signal, window, low, high, speed)
        gains[f"{low:.4f}-{high:.4f}"] = observed / (RMS_UM * 1e-6)
        print(f"  calibration band {index}: {summary['result_status']} gates "
              f"{sum(summary['gates'].values())}/{len(summary['gates'])} bin count {bins:3d}  "
              f"rms {observed:8.4f} m/s2  mean pen {np.mean(penetrations) * 1e6:6.2f} um  "
              f"gain {gains[f'{low:.4f}-{high:.4f}']:9.1f} (m/s2)/m")

    report = {"route": "straight", "speed_kmh": SPEED_KMH, "rms_um": RMS_UM,
              "calibration_seed": CALIBRATION_SEED, "test_seeds": list(TEST_SEEDS),
              "channel": names_channel, "gate_db": GATE_DB, "gains": gains, "tests": []}
    hits = 0
    predictions = 0
    for seed in TEST_SEEDS:
        track, truth = record(seed, band_index=None, edges=edges)
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
        signal = result.accelerations[mask, result.acceleration_names.index(names_channel)]
        penetrations = [result.contacts[i]["axle1_left"].geometry.penetration_m
                        for i in np.nonzero(mask)[0]
                        if result.contacts[i].get("axle1_left") is not None
                        and result.contacts[i]["axle1_left"].geometry is not None]
        mean_pen = float(np.mean(penetrations)) * 1e6
        print(f"\n  test seed {seed}: {summary['result_status']}, mean pen {mean_pen:.2f} um")
        entry = {"seed": seed, "mean_penetration_um": mean_pen, "bands": []}
        for low, high in edges:
            observed, _ = band_rms(signal, window, low, high, speed)
            recovered = observed / gains[f"{low:.4f}-{high:.4f}"]
            applied = RMS_UM * 1e-6
            db = 20.0 * math.log10(recovered / applied)
            ok = abs(db) <= GATE_DB
            hits += int(ok)
            predictions += 1
            entry["bands"].append({"band": f"{low:.4f}-{high:.4f}", "recovered_um": recovered * 1e6,
                                   "applied_um": RMS_UM, "error_db": db, "within_gate": bool(ok)})
            print(f"    {low:.4f}-{high:.4f} m: {recovered * 1e6:6.2f} um of {RMS_UM:.2f} um  "
                  f"({db:+6.2f} dB)  {'PASS' if ok else 'FAIL'}")
        report["tests"].append(entry)

    report["hits"] = hits
    report["predictions"] = predictions
    report["verdict"] = "pass" if hits == predictions else "degraded"
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n  band hit rate: {hits}/{predictions}  -> verdict: {report['verdict'].upper()}")
    print(f"  wrote {args.json}")
    return 0 if hits == predictions else 1


if __name__ == "__main__":
    raise SystemExit(main())
