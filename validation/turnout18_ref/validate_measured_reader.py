"""Validate the measured reader against the campaign's own published statistics.

The campaign reported 99.9th-percentile CH01 (vertical wheel-rail force at the straight
stock rail, kN) of 114.50 / 115.06 / 119.30 kN for the three 30 km/h uphill passes.  If our
reader reproduces those numbers from the raw text files, the measured pipeline is validated
end to end (format, units, calibration factor, channel map) against an independent result.

Also checks CH13 (crossing vertical displacement, mm) against the published 1.618-1.912 mm.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.io.measured import read_channel

ROOT = Path(r"E:\齿轨测试数据") / "轮轨力和位移采集" / "30kmh"
CASES = ("30kmh-SP-1", "30kmh-SP-2", "30kmh-SP-3")
PUBLISHED_CH01_KN = (114.50, 115.06, 119.30)
PUBLISHED_CH13_MM = (1.618, 1.912)


def percentile_999(values: np.ndarray) -> float:
    # validated convention (docs/MEASURED_VALIDATION_2026-10-21.md): |v| p99.9 inside
    # the pass window; the channel is bipolar and the wheel load sits on the negative lobe
    return float(np.percentile(np.abs(values), 99.9))


def main() -> int:
    rows = []
    for folder, published in zip(CASES, PUBLISHED_CH01_KN):
        path = ROOT / folder
        time_s, values = read_channel(path, 1)
        values = np.asarray(values, dtype=float)
        rate = float((values.size - 1) / (time_s[-1] - time_s[0]))
        measured = percentile_999(values)
        rows.append({
            "case": folder,
            "samples": int(values.size),
            "fs_hz": rate,
            "unit": "kN",
            "p99_9": measured,
            "published": published,
            "error_percent": 100.0 * (measured / published - 1.0),
        })
        print(f"{folder:<14} n {values.size:>8} fs {rate:.1f} "
              f"p99.9 {measured:7.2f} published {published:7.2f} "
              f"err {rows[-1]['error_percent']:+.2f} %")

    displaced = []
    for folder in CASES:
        path = ROOT / folder
        time_s, values = read_channel(path, 13)
        values = np.asarray(values, dtype=float)
        peak = float(np.max(np.abs(values)))
        displaced.append({"case": folder, "peak": peak, "unit": "mm"})
        print(f"{folder:<14} CH13 peak {peak:.3f} mm")

    low, high = PUBLISHED_CH13_MM
    inside = all(low <= item["peak"] <= high for item in displaced)
    print(f"\npublished CH13 range {low:.3f}-{high:.3f} mm -> inside {inside}")
    worst = max(abs(row["error_percent"]) for row in rows)
    print(f"worst CH01 error {worst:.2f} %")

    payload = {
        "ch01": rows,
        "ch13": displaced,
        "ch13_inside_published_range": inside,
        "worst_ch01_error_percent": worst,
    }
    out = Path(__file__).resolve().parent / "measured_validation.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if worst < 2.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
