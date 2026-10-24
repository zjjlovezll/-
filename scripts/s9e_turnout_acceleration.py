# -*- coding: utf-8 -*-
"""S9-3b: is the 300-400 Hz elastic band there on a *turnout* run that is long enough to see it?

The straight-window check (S9-3) found the band but 4.5 decades below the channel rms, and the
0.05 s frog window could not answer at all: 101 samples give 19.8 Hz resolution, the 300-400 Hz
band is five bins wide, and a rigid five-coordinate wheelset still reads 10.6 m/s^2 of "300-400 Hz"
from impact leakage.  So the same turnout is run for 0.45 s, which is nine times longer, and the
band is measured on the wheelset (the rigid inline vehicle has no axle-box body) with the start-up
transient excluded.

Two runs: rigid and flexible, on `case_frog_N_strip05.json`.  The output is a table, not a
conclusion - the conclusion goes in the doc with the numbers it rests on.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
REPO = Path(r"F:\ai道岔状态反演辨识\Velch")
sys.path.insert(0, str(REPO / "scripts"))

import s9_compare as compare  # noqa: E402

WORK = Path(r"F:\velch_tmp\s9e")
DURATION_S = 0.45
CHANNEL = "axle1_z_acc_m_per_s2"


def band_rms(values: np.ndarray, rate: float, low: float, high: float) -> float:
    window = np.hanning(len(values))
    spectrum = np.abs(np.fft.rfft((values - values.mean()) * window)) * (
        2.0 / float(np.sum(window)))
    bins = np.fft.rfftfreq(len(values), d=1.0 / rate)
    keep = (bins >= low) & (bins <= high)
    return float(np.sqrt(np.sum(spectrum[keep] ** 2) / 2.0))


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, flexible in (("rigid", False), ("flexible", True)):
        case = compare.build(compare.FROG, WORK / f"case_{label}.json", flexible, DURATION_S)
        out = WORK / f"out_{label}"
        loaded, result, elapsed, manifest = compare.run_case(case, out)
        history = result.to_history(loaded) if hasattr(result, "to_history") else None
        if history is None:
            from velch.io.history import read_history
            history = read_history(out / "history.csv")
        print(f"  {label}: simulated in {elapsed:.1f} s")
        time = compare.history_row(history, "time_s")
        rate = 1.0 / float(np.mean(np.diff(time)))
        values = compare.history_row(history, CHANNEL)
        late = time >= time[0] + 0.5 * (time[-1] - time[0])
        late_values = values[late]
        status = manifest["summary"]["result_status"]
        entry = {
            "status": status, "samples": int(len(values)), "resolution_hz": rate / len(values),
            "late window s": [float(time[late][0]), float(time[late][-1])],
            "max penetration um": compare.penetration(history) * 1e6,
            "rms all": float(np.std(values)) / 9.80665,
            "rms late": float(np.std(late_values)) / 9.80665,
            "peak late g": float(np.max(np.abs(late_values))) / 9.80665,
            "300-400 Hz rms late": band_rms(late_values, rate, 300.0, 400.0),
            "families": compare.spectral_peaks(history, CHANNEL, 6),
        }
        results[label] = entry
        print(f"\n{label}: {status}, {len(values)} samples, resolution "
              f"{entry['resolution_hz']:.1f} Hz, penetration {entry['max penetration um']:.2f} um")
        print(f"  late window {entry['late window s'][0]:.3f}-{entry['late window s'][1]:.3f} s: "
              f"rms {entry['rms late']:.3f} g, peak {entry['peak late g']:.2f} g, "
              f"300-400 Hz rms {entry['300-400 Hz rms late']:.5f}")
        print("  strongest: " + ", ".join(f"{hz:.0f} Hz ({amplitude:.4f})"
                                          for hz, amplitude in entry["families"]))
    if "rigid" in results and "flexible" in results:
        ratio = (results["flexible"]["300-400 Hz rms late"]
                 / max(results["rigid"]["300-400 Hz rms late"], 1e-30))
        results["band ratio flexible/rigid"] = ratio
        print(f"\n300-400 Hz ratio flexible/rigid: {ratio:.2f}x")
    (WORK / "acceleration.json").write_text(json.dumps(results, indent=2, default=float),
                                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
