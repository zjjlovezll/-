"""Identify the suspension modes from the measured axle-box record (SSI-FCM), and compare to the model.

Why this exists: the measurement chain has no excitation log and no profile truth, so the model cannot be
fitted to it directly.  What the record does carry is the system's own modal signature, and that is a
falsifiable check on the model's vertical dynamics -- if the model puts its axle-box resonances somewhere
the measurement does not, the model's stiffnesses are wrong and no amount of inversion tuning will fix it.

Run:  python -X utf8 scripts/s21_oma_measured.py [--section S2] [--record Run_75.mat]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

WORK = Path(r"F:\velch_tmp\oma")
RECORDS = Path(r"F:\ai道岔状态反演辨识\75kmh数据")
SAMPLE_RATE_HZ = 4000.0
BAND_HZ = (5.0, 200.0)
BLOCK_ROWS = 12
SEGMENTS = 8

# Mode frequencies the model produces for the same vehicle (from the modal audits of rounds 55-61):
# the eight restrained axle boxes put a 12.0/12.2/12.6 Hz group on the vertical channel, a single box on
# its primary spring sits at sqrt(1.176e6/48.2)/2pi = 24.9 Hz, and the wheel-disc pair is at 133.3 Hz.
MODEL_MODES_HZ = {
    "box_bounce_group": 12.0,
    "box_on_primary": 24.86,
    "wheel_disc_pair": 133.34,
}


def load_record(name: str) -> dict:
    from scipy.io import loadmat

    path = RECORDS / name
    if not path.exists():
        raise SystemExit(f"record not found: {path}")
    data = loadmat(str(path), squeeze_me=True, variable_names=["Vi_y", "Vi_Speed", "Vi_pks", "Vi_t"])
    vertical = np.asarray(data["Vi_y"], dtype=float)
    speed = np.asarray(data["Vi_Speed"], dtype=float).ravel()
    mileage = np.asarray(data["Vi_pks"], dtype=float).ravel() * 1000.0  # the file is in km
    # ``Vi_Speed`` is recorded in km/h by the same acquisition that logs the 75 km/h run -- reading it as
    # m/s printed 279 km/h for a 75 km/h pass, which is how this was caught.  Keep both units explicit.
    return {"vertical": vertical, "speed_kmh": speed, "mileage_m": mileage, "path": path}


def section(data: dict, start_m: float, stop_m: float) -> dict:
    mask = (data["mileage_m"] >= start_m) & (data["mileage_m"] <= stop_m)
    if np.count_nonzero(mask) < 8_000:
        raise SystemExit(f"section {start_m}-{stop_m} m carries only {np.count_nonzero(mask)} samples; "
                         f"a section must span at least 2 s at {SAMPLE_RATE_HZ:.0f} Hz")
    return {"vertical": data["vertical"][mask], "speed_kmh": data["speed_kmh"][mask],
            "samples": int(np.count_nonzero(mask))}


def prepare(block: dict) -> np.ndarray:
    from scipy.signal import butter, detrend, sosfiltfilt

    values = np.asarray(block["vertical"], dtype=float)
    values = values - values.mean(axis=0, keepdims=True)
    values = detrend(values, axis=0, type="linear")
    low, high = BAND_HZ
    sos = butter(4, [low / (SAMPLE_RATE_HZ / 2.0), high / (SAMPLE_RATE_HZ / 2.0)], btype="band", output="sos")
    return sosfiltfilt(sos, values, axis=0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", default="Run_75kmh_E1toE2.mat")
    parser.add_argument("--section", default="S2")
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    from velch.inverse.oma import identify

    sections = {
        "S1": (4243.0, 4300.0), "S2": (4718.0, 4805.0), "S3": (4855.0, 4927.0),
        "S4": (5250.0, 5352.0), "S5": (5438.0, 5577.0), "S6": (5729.0, 5829.0),
    }
    if args.section != "ALL" and args.section not in sections:
        raise SystemExit(f"unknown section {args.section}: choose from {sorted(sections)} or ALL")

    data = load_record(args.record)
    if args.section == "ALL":
        # The whole pass: 145 s of record, so eight stationary segments are honest here in a way they are
        # not on a 4 s section.  This is the control that says whether a failure is the record's length.
        start_m = float(data["mileage_m"][0])
        stop_m = float(data["mileage_m"][-1])
        block = {"vertical": data["vertical"], "speed_kmh": data["speed_kmh"],
                 "samples": int(data["vertical"].shape[0])}
    else:
        start_m, stop_m = sections[args.section]
        block = section(data, start_m, stop_m)
    signal = prepare(block)
    speed_kmh = float(np.mean(block["speed_kmh"]))
    print(f"record {args.record}: {data['vertical'].shape[0]} samples at {SAMPLE_RATE_HZ:.0f} Hz")
    print(f"section {args.section}: {start_m:.0f}-{stop_m:.0f} m, {block['samples']} samples, "
          f"mean speed {speed_kmh:.2f} km/h ({speed_kmh / 3.6:.2f} m/s)")
    print(f"band {BAND_HZ[0]:.0f}-{BAND_HZ[1]:.0f} Hz, block rows {BLOCK_ROWS}, "
          f"segments {int(min(SEGMENTS, max(2, block['samples'] // 4_000)))}")

    # A short section cannot be cut into eight stationary pieces; scale the averaging instead of
    # pretending the record is longer than it is.
    segments = int(min(SEGMENTS, max(2, block["samples"] // 4_000)))
    result = identify(signal, sample_rate_hz=SAMPLE_RATE_HZ, minimum_frequency_hz=BAND_HZ[0],
                      maximum_frequency_hz=BAND_HZ[1], block_rows=BLOCK_ROWS, segments=segments)
    print(f"\norders tried {result.orders_tried}, entropy order {result.order}, "
          f"poles {result.poles_stable} stable of {result.poles_total}")
    print("\nidentified modes (measurement):")
    for mode in result.modes:
        print(f"  {mode.frequency_hz:8.3f} Hz  zeta {mode.damping_ratio:+.4f}  "
              f"mac {mode.mac:.3f}  poles {mode.poles:3d}  spread {mode.frequency_spread_hz:.3f} Hz")

    print("\ncomparison against the model (same vehicle):")
    comparisons = []
    found = np.array([mode.frequency_hz for mode in result.modes])
    for name, target in MODEL_MODES_HZ.items():
        if found.size == 0:
            print(f"  {name:20s} model {target:8.2f} Hz -> nothing identified")
            continue
        nearest = float(found[np.argmin(np.abs(found - target))])
        relative = (nearest - target) / target * 100.0
        within = abs(relative) < 15.0
        print(f"  {name:20s} model {target:8.2f} Hz  nearest measured {nearest:8.3f} Hz  "
              f"({relative:+.1f} %)  {'AGREES' if within else 'DISAGREES'} at the 15 % bar")
        comparisons.append({"name": name, "model_hz": target, "measured_hz": nearest,
                            "relative_percent": relative, "agrees": within})

    payload = {
        "record": args.record,
        "section": args.section,
        "section_m": [start_m, stop_m],
        "mean_speed_kmh": speed_kmh,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "band_hz": BAND_HZ,
        "identification": result.as_dict(),
        "model_comparison": comparisons,
    }
    target = Path(args.json) if args.json else WORK / f"oma_{args.section}_{Path(args.record).stem}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\nwritten {target}")

    agreeing = sum(1 for row in comparisons if row["agrees"])
    print(f"VERDICT: {agreeing} of {len(comparisons)} model modes are matched by the measurement "
          f"within 15 %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
