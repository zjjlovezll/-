"""Event shape comparison: measured CH01/CH13 vs the Velch frog-window response.

Two corrections matter here and are applied explicitly:

1. **The measured channels are already low-pass filtered** by the campaign pipeline
   (acceleration 5 Hz, displacement 10 Hz - see the campaign processing note).  A raw
   simulation output therefore cannot be compared to them: the ~545 Hz contact ringing in the
   Velch force would be invisible in the measured data.  So the Velch signals are filtered
   with the same corner frequency before their shape is described.
2. **Amplitudes belong to different objects** (rack-railway vehicle on a No. 7 turnout vs
   CRH380A on a No. 18 turnout).  Only durations and oscillation counts are compared.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from velch.inverse.events import compare_shapes, describe_event
from velch.io.measured import condition_windows, lowpass, read_channel

ROOT = Path(r"E:\齿轨测试数据")
MEASURED = ROOT / "轮轨力和位移采集" / "30kmh"
WINDOWS_CSV = ROOT / "实测数据出图代码" / "condition_windows.csv"
CASES = ("30kmh-SP-1", "30kmh-SP-2", "30kmh-SP-3")
VELCH = (Path(__file__).resolve().parent.parent / "crh380a_m" / "out_full12_cap05"
         / "history.csv")
FROG_START, FROG_END = 78.8, 82.2
FORCE_CORNER_HZ = 5.0
DISP_CORNER_HZ = 10.0


def read_windows() -> dict[str, tuple[float, float]]:
    with WINDOWS_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["folder"]: (float(row["event_start_s"]), float(row["event_end_s"]))
            for row in rows}


def read_history(path: Path) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = {name: [] for name in (reader.fieldnames or [])}
        for row in reader:
            for name, value in row.items():
                columns[name].append(float(value))
    time = np.asarray(columns["time_s"], dtype=float)
    return time, {name: np.asarray(values, dtype=float) for name, values in columns.items()}


def main() -> int:
    windows = read_windows()
    time_v, columns = read_history(VELCH)
    rate = 1.0 / float(np.median(np.diff(time_v)))
    station = columns["axle1_x_m"]
    frog = np.nonzero((station >= FROG_START) & (station <= FROG_END))[0]
    print(f"Velch: {station.size} samples at {rate:.0f} Hz, frog window {frog.size} samples, "
          f"x {station[frog[0]]:.2f}..{station[frog[-1]]:.2f} m")

    force_raw = columns["axle1_right_normal_n"]
    axle_raw = columns["axle1_z_m"]
    force_filtered = lowpass(force_raw, rate, FORCE_CORNER_HZ)
    axle_filtered = lowpass(axle_raw, rate, DISP_CORNER_HZ)
    offset = time_v[frog] - time_v[frog[0]]
    velch_force_raw = describe_event(offset, force_raw[frog])
    velch_force = describe_event(offset, force_filtered[frog])
    velch_axle = describe_event(offset, axle_filtered[frog])
    print("\nVelch (raw vs campaign-filtered):")
    print("  " + velch_force_raw.summary(unit="N", label="rail force raw    "))
    print("  " + velch_force.summary(unit="N", label=f"rail force @{FORCE_CORNER_HZ:.0f}Hz"))
    print("  " + velch_axle.summary(unit="m", label=f"axle z   @{DISP_CORNER_HZ:.0f}Hz"))

    rows = []
    print("\nmeasured (already filtered by the campaign pipeline):")
    for name in CASES:
        start, stop = windows[name]
        for channel, label, unit in ((1, "CH01 rail force", "kN"), (13, "CH13 frog disp", "mm")):
            time_s, values = read_channel(MEASURED / name, channel)
            time_s = np.asarray(time_s, dtype=float)
            values = np.asarray(values, dtype=float)
            mask = np.nonzero((time_s >= start) & (time_s <= stop))[0]
            descriptor = describe_event(time_s[mask] - time_s[mask[0]], values[mask])
            rows.append({"case": name, "channel": channel, "unit": unit,
                         "descriptor": descriptor.report()})
            print(f"  {name:<12} {label:<16} " + descriptor.summary(unit=unit))

    print("\nshape ratios (measured / Velch, both at the campaign filter setting):")
    pairs = {1: velch_force, 13: velch_axle}
    for row in rows:
        reference = pairs[row["channel"]]
        rebuilt = type(reference)(**row["descriptor"])
        ratios = compare_shapes(reference, rebuilt)
        row["ratios"] = ratios
        print(f"  {row['case']:<12} CH{row['channel']:02d}  rise {ratios['rise_ratio']:7.2f}x"
              f"  decay {ratios['decay_ratio']:7.2f}x  osc {ratios['oscillation_ratio']:5.2f}x")

    payload = {
        "velch_force_raw": velch_force_raw.report(),
        "velch_force_filtered": velch_force.report(),
        "velch_axle_filtered": velch_axle.report(),
        "filter": {"force_corner_hz": FORCE_CORNER_HZ, "displacement_corner_hz": DISP_CORNER_HZ},
        "measured": rows,
    }
    out = Path(__file__).resolve().parent / "event_shapes.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
