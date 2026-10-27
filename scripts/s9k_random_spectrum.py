"""Invert a random irregularity spectrum from the axle-box acceleration, and score it per band.

The question: given a *random* track (not a single sinusoid), can the axle-box acceleration be
turned back into the spectrum that produced it, and how close is the answer?  Two designs run
here, because they answer different questions:

* ``german_low`` — the realistic case.  Almost all of its variance sits in the 12.5-25 m band,
  so an "overall" number would be a long-wave number whatever the short bands do.
* ``flat`` — the same rms in every octave band.  Only this one can measure the *short*-wave
  accuracy, because it puts energy where the realistic spectrum has none.

Protocol (the one the user described: learn the transfer on known random tracks, apply it to an
unknown one):

1. calibration run on seed A: ``G(band) = rms(a_band) / rms(r_band)`` — a measured transfer per
   octave band, no assumed model;
2. test run on seed B: ``r_hat(band) = rms(a_band) / G(band)``, compared with the truth from the
   file;
3. background run with **no** excitation: the same band powers are the measurement floor, so a
   band whose signal does not clear it by 10 dB is reported as "not measurable" rather than as
   an error of the method.

Criteria fixed before the runs: ``|20 log10(r_hat / r_true)| <= 2 dB`` is "quantitative"; bands
carrying >= 5 % of the variance must all pass; a band below the SNR gate is reported separately
and excluded from the aggregate.

    python -X utf8 scripts/s9k_random_spectrum.py            # both designs
    python -X utf8 scripts/s9k_random_spectrum.py german_low # one of them
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
WORK = pathlib.Path(r"F:\velch_tmp\s9k")
BASE = pathlib.Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
VEHICLE = "CRH380A_M_axlebox"
SPEED_KMH = 80.0
DURATION_S = 3.0
X_START_M = 30.0
LENGTH_M = 200.0
TRE_STEP_M = 0.005          # 10 samples per 50 mm period
SHORTEST_M = 0.05
LONGEST_M = 12.5
OUTPUT_STEP_S = 2.0e-4      # 5 kHz
SOLVER_STEP_S = 1.0e-4
CHANNEL = "axle1_box_left_z_acc_m_per_s2"
SNR_GATE_DB = 10.0
SEED_CALIBRATION = 20261025
SEED_TEST = 20261026
FLAT_RMS_M = 5.0e-6         # every octave band at 5 um (0.005 mm)
# The test track must NOT have the same per-band amplitudes as the calibration track.  With two
# statistically identical random tracks the inversion collapses to "recovered = calibration
# band rms" whenever a common start-up transient dominates the channel -- it then reports 0.0 %
# error while measuring nothing (this happened in the first version of this script).
TEST_SCALES = (2.20, 0.45, 1.70, 0.55, 2.40, 0.60, 1.80, 0.40)
WINDOW_START = 0.40         # skip the start-up transient: analyse the last 60 % of the record


def octave_bands() -> list[tuple[float, float]]:
    """(short, long) metre bands, one octave each, from SHORTEST_M up to LONGEST_M."""

    bands: list[tuple[float, float]] = []
    short = SHORTEST_M
    while short < LONGEST_M - 1e-12:
        bands.append((short, min(2.0 * short, LONGEST_M)))
        short *= 2.0
    return bands


def flat_track(*, seed: int, scales: tuple[float, ...] | None = None):
    """Equal rms in every octave band: the only design that can measure the short waves."""

    from velch.irregularity import IrregularityTrack

    count = int(round(LENGTH_M / TRE_STEP_M)) + 1
    s_m = np.arange(count, dtype=float) * TRE_STEP_M
    omega = 2.0 * np.pi * np.fft.rfftfreq(count, d=TRE_STEP_M)      # rad/m
    phase_seed = np.random.default_rng(seed)
    spectrum = np.zeros_like(omega)
    for low, high in octave_bands():
        inside = (omega >= 2.0 * np.pi / high) & (omega < 2.0 * np.pi / low)
        if not np.any(inside):
            continue
        # one-dimensional random phase, unit power per bin, then scaled to the band rms
        line = phase_seed.normal(size=int(inside.sum()))
        spectrum[inside] = line
    # sum the bands, each at the same rms: that is what makes every octave equally important
    total = np.zeros(count)
    for position, (low, high) in enumerate(octave_bands()):
        inside = (omega >= 2.0 * np.pi / high) & (omega < 2.0 * np.pi / low)
        component = np.fft.irfft(np.where(inside, spectrum, 0.0), n=count)
        deviation = float(component.std())
        if deviation < 1e-18:
            continue
        scale = 1.0 if scales is None else scales[position % len(scales)]
        total += component / deviation * FLAT_RMS_M * scale
    return IrregularityTrack(
        s_m=s_m,
        lateral_m=np.zeros_like(s_m),
        vertical_m=total,
        roll_rad=np.zeros_like(s_m),
        gauge_m=np.zeros_like(s_m),
        source=f"generated: flat octave bands {SHORTEST_M}-{LONGEST_M} m seed {seed}",
    )


def rescale(track, scales: tuple[float, ...]):
    """Scale each octave band of an existing track: a different spectral shape, same length."""

    from velch.irregularity import IrregularityTrack

    values = np.asarray(track.vertical_m, dtype=float)
    count = len(values)
    spectrum = np.fft.rfft(values - values.mean())
    omega = 2.0 * np.pi * np.fft.rfftfreq(count, d=float(track.step_m))
    total = np.zeros(count)
    for position, (low, high) in enumerate(octave_bands()):
        inside = (omega >= 2.0 * np.pi / high) & (omega < 2.0 * np.pi / low)
        component = np.fft.irfft(np.where(inside, spectrum, 0.0), n=count)
        total += component * scales[position % len(scales)]
    return IrregularityTrack(
        s_m=np.asarray(track.s_m, dtype=float),
        lateral_m=np.zeros_like(total),
        vertical_m=total,
        roll_rad=np.zeros_like(total),
        gauge_m=np.zeros_like(total),
        source=f"generated: {track.source} rescaled per octave",
    )


def german_track(*, seed: int):
    from velch.irregularity_gen import generate

    return generate(
        spectrum_name="german_low",
        length_m=LENGTH_M,
        step_m=TRE_STEP_M,
        shortest_m=SHORTEST_M,
        longest_m=LONGEST_M,
        seed=seed,
        channels=("vertical",),
    )


def zero_track():
    from velch.irregularity import IrregularityTrack

    count = int(round(LENGTH_M / TRE_STEP_M)) + 1
    s_m = np.arange(count, dtype=float) * TRE_STEP_M
    zeros = np.zeros_like(s_m)
    return IrregularityTrack(s_m=s_m, lateral_m=zeros, vertical_m=zeros,
                             roll_rad=zeros, gauge_m=zeros,
                             source="generated: zero (background floor)")


def write_track(track, name: str) -> pathlib.Path:
    from velch.irregularity import write_tre

    path = WORK / f"{name}.tre"
    write_tre(path, track, comment=f"s9k {name}: {track.source}")
    return path


def build_case(tre: pathlib.Path, label: str) -> pathlib.Path:
    doc = json.loads(BASE.read_text(encoding="utf-8"))
    doc.pop("initial_state", None)
    # Keep the case's own inline vehicle block and topology, and force the speed that both the
    # generated track and ``acceleration_band_rms`` assume.
    #
    # Replacing the inline vehicle with ``vehicle_ref`` (the obvious-looking cleanup) silently
    # took the reference model's speed, 97.22 m/s, and cost two experiments.  An 80 km/h track
    # was driven at 350 km/h: the wheels turned at 226 rad/s instead of 51.7, every wavelength
    # band was mapped with a speed 4.4x too low, and a 2 s run reached 224 m while the rail
    # station table ends at 150 m -- from t = 1.1 s the geometry ran off the end of the table and
    # the vehicle sat in a 13 Hz limit cycle.  Every band then looked "below the floor".
    doc["vehicle"]["travel_speed_m_s"] = SPEED_KMH / 3.6
    # The frozen inline topology was written before axle boxes were numbered from zero.
    for body in doc.get("topology", {}).get("bodies", []) or []:
        if body.get("kind") == "axlebox" and isinstance(body.get("axle"), int):
            body["axle"] = body["axle"] - 1
    doc["case_id"] = f"s9k_{label}"
    stations = [float(station["s_m"]) for template in doc["rail_templates"]
                for station in template.get("stations") or []]
    reach = X_START_M + doc["vehicle"]["travel_speed_m_s"] * DURATION_S + 10.0
    if stations and reach > max(stations):
        raise ValueError(
            f"run would leave the rail station table: reach {reach:.1f} m > last station "
            f"{max(stations):.1f} m (x_start {X_START_M:.1f} m, {DURATION_S:.2f} s at "
            f"{doc['vehicle']['travel_speed_m_s']:.2f} m/s, 10 m of axle offsets)"
        )
    doc["run"].update({
        "method": "BDF", "jacobian": "analytic", "rtol": 1e-4, "atol": 1e-8,
        "x_start_m": X_START_M, "duration_s": DURATION_S,
        "output_step_s": OUTPUT_STEP_S, "max_solver_step_s": SOLVER_STEP_S,
    })
    doc["irregularity"] = {
        "tre": str(tre), "start_m": 0.0, "end_m": 1.0e9, "fade_m": 0.0,
        "scale": 1.0, "channels": ["vertical"],
    }
    path = WORK / f"case_{label}.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def profile_band_rms(track) -> dict[str, float]:
    """True rms per octave band, straight from the generated column."""

    values = np.asarray(track.vertical_m, dtype=float)
    step = float(track.step_m)
    spectrum = np.fft.rfft(values - values.mean())
    omega = 2.0 * np.pi * np.fft.rfftfreq(len(values), d=step)
    out: dict[str, float] = {}
    for low, high in octave_bands():
        inside = (omega >= 2.0 * np.pi / high) & (omega < 2.0 * np.pi / low)
        power = float(np.sum(np.abs(spectrum[inside]) ** 2)) * 2.0 / (len(values) ** 2)
        out[f"{low:g}-{high:g}"] = float(np.sqrt(power))
    return out


def acceleration_band_rms(values: np.ndarray, rate_hz: float) -> dict[str, float]:
    """Band rms of one channel over the late part of the record, in wavelength bands.

    The first 40 % is dropped: the wheel starts on an undeflected tread and the resulting
    transient is 2-3 orders larger than the excitation at the long-wave end, so a whole-record
    rms would measure the transient instead of the track.
    """

    speed = SPEED_KMH / 3.6
    x = np.asarray(values, dtype=float)
    x = x[int(WINDOW_START * len(x)):]
    x = x - x.mean()
    window = np.hanning(len(x))
    spectrum = np.fft.rfft(x * window)
    freq = np.fft.rfftfreq(len(x), d=1.0 / rate_hz)
    gain = 2.0 / np.sum(window)
    amplitude = np.abs(spectrum) * gain
    out: dict[str, float] = {}
    for low, high in octave_bands():
        inside = (freq >= speed / high) & (freq < speed / low)
        out[f"{low:g}-{high:g}"] = float(np.sqrt(np.sum(amplitude[inside] ** 2) / 2.0))
    return out


def run(track, label: str) -> dict:
    from velch.io.history import read_history
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

    tre = write_track(track, label)
    case = build_case(tre, label)
    loaded = load_vehicle_case(case)
    started = time.perf_counter()
    result = simulate_vehicle(loaded)
    elapsed = time.perf_counter() - started
    out = WORK / f"out_{label}"
    out.mkdir(exist_ok=True)
    history_path, manifest = save_vehicle_result(loaded, result, out)
    status = json.loads(pathlib.Path(manifest).read_text(encoding="utf-8"))["summary"]["result_status"]
    history = read_history(pathlib.Path(history_path))
    names = list(history.ordering)
    time_s = np.asarray(history.data[names.index("time_s")], dtype=float)
    rate = 1.0 / float(np.mean(np.diff(time_s)))
    values = np.asarray(history.data[names.index(CHANNEL)], dtype=float)
    print(f"{label}: {elapsed:.1f} s, {len(values)} samples at {rate:.0f} Hz -> {status}")
    return {
        "label": label, "tre": str(tre), "case": str(case), "seconds": elapsed,
        "status": status, "rate_hz": rate, "samples": len(values),
        "true_band_rms_m": profile_band_rms(track),
        "acc_band_rms_m_s2": acceleration_band_rms(values, rate),
        "overall_true_rms_m": float(np.sqrt(np.mean(np.square(track.vertical_m)))),
    }


def assess(name: str) -> dict:
    """Calibrate the per-band transfer on one track, invert a differently-shaped track."""

    if name == "flat":
        calibration_track = flat_track(seed=SEED_CALIBRATION)
        test_track = flat_track(seed=SEED_TEST, scales=TEST_SCALES)
    elif name == "german_low":
        calibration_track = german_track(seed=SEED_CALIBRATION)
        test_track = rescale(german_track(seed=SEED_TEST), TEST_SCALES)
    else:
        raise SystemExit(f"unknown design {name!r}: use 'flat' or 'german_low'")

    calibration = run(calibration_track, f"{name}_cal")
    test = run(test_track, f"{name}_test")
    floor = run(zero_track(), f"{name}_floor")

    bands = list(calibration["true_band_rms_m"])
    report: dict[str, object] = {"design": name, "bands": {}}
    transfer: dict[str, float] = {}
    for band in bands:
        truth = calibration["true_band_rms_m"][band]
        measured = calibration["acc_band_rms_m_s2"][band]
        transfer[band] = measured / truth if truth > 0 else float("nan")

    columns = []
    for band in bands:
        true_rms = test["true_band_rms_m"][band]
        acc = test["acc_band_rms_m_s2"][band]
        noise = floor["acc_band_rms_m_s2"][band]
        gain = transfer[band]
        recovered = acc / gain if gain and np.isfinite(gain) and gain > 0 else float("nan")
        snr = 20.0 * np.log10(acc / noise) if noise > 0 and acc > 0 else float("inf")
        error = (recovered - true_rms) / true_rms * 100.0 if true_rms > 0 else float("nan")
        db = 20.0 * np.log10(recovered / true_rms) if true_rms > 0 and recovered > 0 else float("nan")
        columns.append({"band_m": band, "true_um": true_rms * 1e6, "recovered_um": recovered * 1e6,
                        "calibration_um": calibration["true_band_rms_m"][band] * 1e6,
                        "error_percent": error, "error_db": db, "snr_db": snr,
                        "acc_band": acc, "floor_band": noise, "transfer": gain})
        report["bands"][band] = columns[-1]

    variance = {band: entry["true_um"] ** 2 for band, entry in report["bands"].items()}
    total = sum(variance.values()) or 1.0
    print(f"\n== {name}: {test['samples']} samples, {test['seconds']:.0f} s per run, "
          f"test-track overall rms {test['overall_true_rms_m'] * 1e6:.2f} um, "
          f"calibration track {calibration['overall_true_rms_m'] * 1e6:.2f} um")
    print(f"{'band (m)':>12} {'cal':>8} {'true':>8} {'recovered':>10} {'error':>8} {'dB':>6} "
          f"{'SNR':>6} {'share':>6}")
    for entry in columns:
        share = variance[entry['band_m']] / total * 100.0
        flag = "  <-- below the floor" if entry["snr_db"] < SNR_GATE_DB else ""
        print(f"{entry['band_m']:>12} {entry['calibration_um']:8.3f} {entry['true_um']:8.3f} "
              f"{entry['recovered_um']:10.3f} {entry['error_percent']:7.1f}% {entry['error_db']:6.2f} "
              f"{entry['snr_db']:6.1f} {share:5.1f}%{flag}")

    usable = [entry for entry in columns if entry["snr_db"] >= SNR_GATE_DB]
    good = [entry for entry in usable if abs(entry["error_db"]) <= 2.0]
    heavy = [entry for entry in columns if variance[entry["band_m"]] / total >= 0.05]
    print(f"quantitative (|dB| <= 2): {len(good)}/{len(usable)} above-floor bands; "
          f"variance-heavy pass {sum(1 for entry in heavy if abs(entry['error_db']) <= 2.0)}/{len(heavy)}")
    report["summary"] = {
        "usable_bands": len(usable), "quantitative_bands": len(good),
        "heavy_bands": len(heavy),
        "heavy_bands_pass": sum(1 for entry in heavy if abs(entry["error_db"]) <= 2.0),
        "seconds_per_run": test["seconds"],
    }
    return report


def main(argv: list[str]) -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    wanted = argv[1:] or ["german_low", "flat"]
    everything = {}
    for name in wanted:
        everything[name] = assess(name)
    (WORK / "random_spectrum.json").write_text(json.dumps(everything, indent=2), encoding="utf-8")
    print("\nwrote", WORK / "random_spectrum.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
