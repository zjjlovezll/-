"""Which statistic reproduces the campaign's published "99.9 % CH01" force?

The published numbers are 114.50 / 115.06 / 119.30 kN for the three 30 km/h uphill passes,
described as a 99.9th percentile of CH01.  Our raw channel is bipolar (e.g. -122.5 .. +31.6 kN
on pass 1), so a percentile of the signed values gives +17.9 kN - a different quantity.

This script computes several candidate conventions, inside the published pass window:

    abs_peak      max |v| in the window
    neg_peak      max (-v) in the window, i.e. the compressive lobe
    abs_p999      p99.9 of |v| in the window
    neg_p999      p99.9 of (-v) in the window
    pos_p999      p99.9 of (+v) in the window

and reports which one matches all three published values within tolerance.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.io.measured import condition_windows, read_channel

ROOT = Path(r"E:\齿轨测试数据")
MEASURED = ROOT / "轮轨力和位移采集" / "30kmh"
WINDOWS = ROOT / "实测数据出图代码" / "condition_windows.csv"
CASES = ("30kmh-SP-1", "30kmh-SP-2", "30kmh-SP-3")
PUBLISHED = (114.50, 115.06, 119.30)


def window_mean_windows(name: str) -> tuple[float, float]:
    """Read the two windows this script may need from the CSV header."""
    lines = WINDOWS.read_text(encoding="utf-8-sig").splitlines()
    header = lines[0].split(",")
    index = {key: position for position, key in enumerate(header)}
    for line in lines[1:]:
        fields = line.split(",")
        if fields[index["folder"]] != name:
            continue
        event = (float(fields[index["event_start_s"]]), float(fields[index["event_end_s"]]))
        ch01 = (float(fields[index["ch01_event_start_s"]]), float(fields[index["ch01_event_end_s"]]))
        return event, ch01
    raise KeyError(name)


def statistics(values: np.ndarray) -> dict[str, float]:
    magnitude = np.abs(values)
    return {
        "abs_peak": float(magnitude.max()),
        "neg_peak": float((-values).max()),
        "abs_p999": float(np.percentile(magnitude, 99.9)),
        "neg_p999": float(np.percentile(-values, 99.9)),
        "pos_p999": float(np.percentile(values, 99.9)),
    }


def main() -> int:
    table = condition_windows(WINDOWS)
    rows = []
    for name, published in zip(CASES, PUBLISHED):
        time_s, values = read_channel(MEASURED / name, 1)
        time_s = np.asarray(time_s, dtype=float)
        values = np.asarray(values, dtype=float)
        event, ch01 = window_mean_windows(name)
        picked = {}
        for label, (start, stop) in (("event", event), ("ch01", ch01)):
            mask = (time_s >= start) & (time_s <= stop)
            picked[label] = statistics(values[mask])
        whole = statistics(values)
        rows.append({"case": name, "published": published,
                     "csv_window": table.get(name), "event": picked["event"],
                     "ch01": picked["ch01"], "whole": whole})
        print(f"\n{name}  published {published:.2f} kN  window {event[0]:.1f}-{event[1]:.1f} s"
              f"  samples in window {int(((time_s >= event[0]) & (time_s <= event[1])).sum())}")
        for label, stats in (("event", picked["event"]), ("ch01", picked["ch01"]),
                             ("whole", whole)):
            print(f"  {label:<6} abs_peak {stats['abs_peak']:7.2f}  neg_peak {stats['neg_peak']:7.2f}"
                  f"  abs_p999 {stats['abs_p999']:7.2f}  neg_p999 {stats['neg_p999']:7.2f}"
                  f"  pos_p999 {stats['pos_p999']:7.2f}")

    print("\nmatching convention (all three within 3 %):")
    verdicts = {}
    for label in ("event", "ch01", "whole"):
        for stat in ("abs_peak", "neg_peak", "abs_p999", "neg_p999", "pos_p999"):
            errors = [100.0 * (row[label][stat] / row["published"] - 1.0) for row in rows]
            worst = max(abs(value) for value in errors)
            verdicts[f"{label}.{stat}"] = {"errors_percent": errors, "worst": worst}
            if worst < 3.0:
                print(f"  MATCH {label}.{stat}: errors {errors[0]:+.2f} / {errors[1]:+.2f}"
                      f" / {errors[2]:+.2f} %")
    best = min(verdicts.items(), key=lambda item: item[1]["worst"])
    print(f"  closest overall: {best[0]} (worst {best[1]['worst']:.2f} %)")

    payload = {"cases": rows, "verdicts": verdicts, "closest": best[0]}
    out = Path(__file__).resolve().parent / "measured_convention.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
