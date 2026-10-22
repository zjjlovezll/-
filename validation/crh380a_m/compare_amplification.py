"""Like-for-like comparison: dynamic amplification (peak / running mean) on both sides.

Absolute force levels are not comparable yet -- the measured CH01 is a stock-rail gauge bridge
whose influence line (measurement section, direction) is explicitly missing from the campaign
documentation, while the simulated 49.71 kN is one wheel/one rail contact force.  What *is*
comparable is the amplification: how much the passage peak exceeds the steady rolling level.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.io.measured import event_window, read_channel

ROOT = Path(r"E:\齿轨测试数据\轮轨力和位移采集")
CONDITIONS = ("30kmh/30kmh-SP-1", "30kmh/30kmh-SP-2", "30kmh/30kmh-SP-3",
              "25kmh-SP-1", "25kmh-SP-2", "25kmh-SP-3")
BASE = Path(__file__).resolve().parent


def main() -> int:
    simulated = json.loads((BASE / "rack_simpack_contact.json").read_text(encoding="utf-8"))
    rows = []
    print("measured (CH01, campaign calibration not applied):")
    for name in CONDITIONS:
        time, force = read_channel(ROOT / name, 1)
        window = event_window(time, np.abs(force))
        inside = (time >= window[0]) & (time <= window[1])
        passage = np.abs(force[inside])
        steady = float(np.percentile(passage, 50))
        peak = float(np.percentile(passage, 99.9))
        ratio = peak / steady if steady else float("nan")
        rows.append({"condition": name, "steady_kn": steady, "peak_kn": peak,
                     "amplification": ratio})
        print(f"  {name:<22} steady {steady:6.2f} kN  peak {peak:7.2f} kN  "
              f"amplification {ratio:5.2f}")

    print("\nsimulated (per wheel / per rail contact force):")
    for side in ("R", "L"):
        data = simulated["sides"][side]
        mean = data["mean_n"] / 1e3
        peak = data["max_n"] / 1e3
        print(f"  {side}: mean {mean:6.2f} kN  peak {peak:7.2f} kN  "
              f"amplification {peak / mean if mean else float('nan'):5.2f}")

    measured_mean = float(np.mean([row["amplification"] for row in rows[:3]]))
    sim = simulated["sides"]["R"]
    sim_ratio = sim["max_n"] / sim["mean_n"]
    print(f"\namplification, measured 30 km/h mean {measured_mean:.2f} "
          f"vs simulated right rail {sim_ratio:.2f}"
          f"  -> difference {100.0 * (sim_ratio / measured_mean - 1.0):+.1f} %")

    payload = {"measured": rows,
               "simulated": {side: {"mean_kn": simulated["sides"][side]["mean_n"] / 1e3,
                                    "peak_kn": simulated["sides"][side]["max_n"] / 1e3,
                                    "amplification": (simulated["sides"][side]["max_n"]
                                                      / simulated["sides"][side]["mean_n"])}
                             for side in ("L", "R")},
               "measured_amplification_mean": measured_mean,
               "simulated_amplification_right": sim_ratio,
               "difference_percent": 100.0 * (sim_ratio / measured_mean - 1.0)}
    (BASE / "rack_amplification.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
