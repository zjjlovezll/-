"""Frequency-domain decomposition of the measured axle boxes, judged by cross-section repetition.

The criterion is not "is there a peak" but "does the same peak appear in section after section".  A mode of
the vehicle is a property of the vehicle, so it must survive a change of track section; a peak that lives in
one section only is the track, not the vehicle.

Run:  python -X utf8 scripts/s22_fdd_measured.py
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
SECTIONS = {
    "S1": (4243.0, 4300.0), "S2": (4718.0, 4805.0), "S3": (4855.0, 4927.0),
    "S4": (5250.0, 5352.0), "S5": (5438.0, 5577.0), "S6": (5729.0, 5829.0),
}
MATCH_TOLERANCE = 0.03  # 3 % relative, the same bar the model comparison uses


def load(path: Path) -> dict:
    from scipy.io import loadmat

    data = loadmat(str(path), squeeze_me=True, variable_names=["Vi_y", "Vi_Speed", "Vi_pks"])
    return {
        "vertical": np.asarray(data["Vi_y"], dtype=float),
        "speed_kmh": np.asarray(data["Vi_Speed"], dtype=float).ravel(),
        "mileage_m": np.asarray(data["Vi_pks"], dtype=float).ravel() * 1000.0,
    }


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
    print(f"record {Path(args.record).name}: {record['vertical'].shape[0]} samples at "
          f"{SAMPLE_RATE_HZ:.0f} Hz, {record['vertical'].shape[1]} channels")

    blocks: dict[str, np.ndarray] = {}
    for name, (start_m, stop_m) in SECTIONS.items():
        mask = (record["mileage_m"] >= start_m) & (record["mileage_m"] <= stop_m)
        samples = int(np.count_nonzero(mask))
        if samples < int(2.0 * SAMPLE_RATE_HZ):
            print(f"  {name}: skipped ({samples} samples)")
            continue
        blocks[name] = prepare(record["vertical"][mask])
    blocks["ALL"] = prepare(record["vertical"])

    found: dict[str, list[float]] = {}
    payload = {"record": Path(args.record).name, "sections": {}}
    for name, signal in blocks.items():
        decomposition = spectral_matrix(signal, sample_rate_hz=SAMPLE_RATE_HZ,
                                       segment_seconds=SEGMENT_SECONDS, band=BAND_HZ)
        peaks = find_peaks(decomposition, prominence_db=PROMINENCE_DB)
        found[name] = [peak.frequency_hz for peak in peaks]
        payload["sections"][name] = decomposition.as_dict()
        print(f"\n{name}: {signal.shape[0] / SAMPLE_RATE_HZ:.1f} s, resolution "
              f"{decomposition.resolution_hz:.3f} Hz, {len(peaks)} peak(s)")
        for peak in peaks:
            print(f"  {peak.frequency_hz:8.3f} Hz  prominence {peak.prominence_db:6.2f} dB  "
                  f"shape {peak.shape_ratio:.2f}  upper/first {peak.upper_singular_ratio:.2f}")

    real = [name for name in SECTIONS if name in found]
    print(f"\ncross-section repetition (tolerance {MATCH_TOLERANCE * 100:.0f} %, over {len(real)} sections):")
    rows = []
    for name in sorted({value for values in found.values() for value in values}):
        hits = []
        for section in real:
            values = np.asarray(found[section])
            if values.size == 0:
                continue
            nearest = float(values[np.argmin(np.abs(values - name))])
            if abs(nearest - name) / name <= MATCH_TOLERANCE:
                hits.append(section)
        rows.append({"frequency_hz": name, "sections": hits, "count": len(hits)})
    for row in sorted(rows, key=lambda item: item["count"], reverse=True):
        print(f"  {row['frequency_hz']:8.3f} Hz  in {row['count']}/{len(real)} "
              f"({', '.join(row['sections']) or '-'})")
    repeated = [row for row in rows if row["count"] >= max(2, len(real) // 2 + 1)]
    payload["repetition"] = rows
    payload["repeated_modes_hz"] = sorted(row["frequency_hz"] for row in repeated)

    print(f"\nVERDICT: {len(repeated)} frequency(ies) repeat in at least half the sections: "
          f"{[round(row['frequency_hz'], 3) for row in repeated]}")
    target = Path(args.json) if args.json else WORK / "fdd_sections.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"written {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
