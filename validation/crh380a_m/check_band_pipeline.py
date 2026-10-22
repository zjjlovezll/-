"""Verify our band pipeline reproduces the campaign's own published numbers.

The campaign's ``30kmh_加速度_标准口径_20261019/处理说明.md`` publishes, for 30 km/h up-slope,
peak / peak-to-peak / RMS (m/s^2, 5-1000 Hz) per acceleration channel.  Those are an *independent
implementation* of the same convention, so matching them is a real check of ``velch.inverse.bands``
-- and it is turnout-independent, which matters because the measured turnout is not the modelled one.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.inverse.bands import band_metrics
from velch.io.measured import event_window, read_channel

MEASURED = Path(r"E:\齿轨测试数据\加速度采集\30KMH-SP-1")
RATE_HZ = 5120.0
BASE = Path(__file__).resolve().parent

# 处理说明.md section 三, SP-1 row set (peak / peak-to-peak / RMS, m/s^2)
PUBLISHED = {
    1: (108.21, 215.45, 7.23),
    2: (47.15, 86.75, 3.63),
    3: (120.05, 225.53, 6.06),
    4: (187.71, 292.12, 4.66),
    5: (442.81, 521.90, 7.95),
    6: (635.66, 1045.02, 16.13),
    7: (476.49, 900.69, 11.29),
}

# 处理说明.md section 四: per-wheelset peak min / median / max (m/s^2) -- the dispersion warning
PUBLISHED_WHEELSET = {
    1: (42.6, 84.6, 108.2),
    2: (8.9, 26.8, 41.9),
    3: (17.0, 38.8, 120.0),
    4: (4.5, 9.3, 187.7),
    5: (142.0, 204.5, 442.8),
    6: (417.0, 494.8, 635.7),
    7: (64.3, 73.2, 476.5),
}


def main() -> int:
    rows: list[dict[str, object]] = []
    print(f"{'CH':>3}  {'ours: peak / p-p / rms':<30} {'published':<26} {'ratio peak':>10}")
    for channel, (peak, span, rms) in PUBLISHED.items():
        time, value = read_channel(MEASURED, channel, repair_clock=True)
        rate = 1.0 / float(np.median(np.diff(time)))
        # the campaign's RMS is taken over the passage window; the record itself is nearly half
        # quiet time, so an unfiltered whole-record RMS would be about half the published value
        window = event_window(time, np.abs(value))
        inside = (time >= window[0]) & (time <= window[1])
        metrics = band_metrics(value[inside], rate)
        ratio = metrics.peak / peak if peak else float("nan")
        print(f"CH{channel:02d}  {metrics.peak:8.2f} {metrics.peak_to_peak:8.2f} "
              f"{metrics.rms:8.2f}   {peak:8.2f} {span:8.2f} {rms:8.2f}   {ratio:10.3f}")
        rows.append({
            "channel": channel,
            "ours": {"peak": metrics.peak, "peak_to_peak": metrics.peak_to_peak,
                     "rms": metrics.rms, "median_abs": metrics.median_abs,
                     "p999_abs": metrics.p999_abs,
                     "dominant_band_hz": metrics.dominant_band_hz},
            "published": {"peak": peak, "peak_to_peak": span, "rms": rms,
                          "wheelset_peak_min_median_max": PUBLISHED_WHEELSET[channel]},
            "ratio_peak": ratio,
        })

    ratios = [row["ratio_peak"] for row in rows if np.isfinite(row["ratio_peak"])]
    payload = {
        "rate_hz_used": "per-channel median dt",
        "channel_rows": rows,
        "peak_ratio_min": float(np.min(ratios)),
        "peak_ratio_max": float(np.max(ratios)),
        "note": ("campaign numbers come from a 5-1000 Hz zero-phase band-pass and a per-wheelset "
                 "peak sequence; agreement within a few percent confirms the shared convention, "
                 "not the same turnout"),
    }
    (BASE / "band_pipeline_check.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\npeak ratio range: {payload['peak_ratio_min']:.3f} .. {payload['peak_ratio_max']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
