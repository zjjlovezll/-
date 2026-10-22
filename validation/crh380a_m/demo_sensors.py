"""Turn one Velch run into the sensor channels a test campaign would have recorded.

The demonstration is deliberately turnout-agnostic: it shows the *pipeline* (history -> sensor
trace -> 5120 Hz -> 5-1000 Hz band convention -> peak / p99.9 in the campaign's own units), which
is the only thing that can be built before the measured turnout and the modelled turnout agree.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.inverse.bands import band_metrics
from velch.inverse.sensors import resample, sensor_table
from velch.io.history import read_history

BASE = Path(__file__).resolve().parent
RUN = BASE / "out_strip_soft"
TARGET_RATE_HZ = 5120.0


def main() -> int:
    history = read_history(RUN / "history.csv")
    traces = sensor_table(history, axles=(1, 2))

    rows = []
    print(f"{'trace':<44} {'unit':<7} {'peak':>10} {'p99.9':>10} {'rms(5-1000)':>11}")
    for trace in traces:
        if trace.unit != "m/s^2":
            continue
        grid, values = resample(trace.time_s, trace.values, TARGET_RATE_HZ)
        metrics = band_metrics(values, TARGET_RATE_HZ)
        print(f"{trace.name:<44} {trace.unit:<7} {metrics.peak:10.3f} "
              f"{metrics.p999_abs:10.3f} {metrics.rms:11.3f}")
        rows.append({
            "name": trace.name,
            "unit": trace.unit,
            "note": trace.note,
            "rate_hz": float(trace.rate_hz),
            "peak": metrics.peak,
            "peak_to_peak": metrics.peak_to_peak,
            "rms_5_1000": metrics.rms,
            "p999_abs": metrics.p999_abs,
            "median_abs": metrics.median_abs,
        })

    payload = {
        "run": str(RUN.relative_to(BASE.parent.parent)),
        "source_rate_hz": float(1.0 / np.median(np.diff(history.time_s))),
        "target_rate_hz": TARGET_RATE_HZ,
        "band_hz": [5.0, 1000.0],
        "traces": rows,
        "limits": {
            "no_axle_box_body": "wheelset acceleration is a lower bound on an axle-box reading",
            "no_station_resolved_rail": "rail DOF is lumped per rail, not per sleeper bay",
            "not_comparable_across_turnouts": "the measured campaign is a different turnout",
        },
    }
    (BASE / "sensor_pipeline_demo.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
