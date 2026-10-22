"""Which channel carries the published 114 kN? Magnitude census of one 30 km/h pass."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from velch.io.measured import read_channel

FOLDER = Path(r"E:\齿轨测试数据\轮轨力和位移采集\30kmh\30kmh-SP-1")

print(f"{'CH':>3} {'n':>8} {'min':>10} {'max':>10} {'p99.9':>10} {'p99.99':>10} {'absmax':>10}")
for channel_index in range(1, 16):
    try:
        time_s, values = read_channel(FOLDER, channel_index)
    except Exception as error:  # noqa: BLE001 - the point is to see what is missing
        print(f"{channel_index:>3} unreadable: {type(error).__name__}: {error}")
        continue
    values = np.asarray(values, dtype=float)
    print(f"{channel_index:>3} {values.size:>8} {values.min():>10.3f} {values.max():>10.3f} "
          f"{np.percentile(values, 99.9):>10.3f} {np.percentile(values, 99.99):>10.3f} "
          f"{np.max(np.abs(values)):>10.3f}")
