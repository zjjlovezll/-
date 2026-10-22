"""Settle the measured raw unit: print percentiles of CH01 for two folders."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from velch.io.measured import read_channel

ROOT = Path(r"E:\齿轨测试数据\轮轨力和位移采集")
FOLDERS = ("25kmh-SP-1", "30kmh/30kmh-SP-1")


def main() -> int:
    for name in FOLDERS:
        folder = ROOT / name
        time, raw = read_channel(folder, 1)
        print(f"\n{name}: n={raw.size} dt={np.median(np.diff(time)):.6g} s")
        for label, value in (("min", raw.min()), ("max", raw.max()),
                             ("abs p50", np.percentile(np.abs(raw), 50)),
                             ("abs p90", np.percentile(np.abs(raw), 90)),
                             ("abs p99", np.percentile(np.abs(raw), 99)),
                             ("abs p99.9", np.percentile(np.abs(raw), 99.9)),
                             ("abs max", np.abs(raw).max())):
            print(f"  {label:<10} {value:14.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
