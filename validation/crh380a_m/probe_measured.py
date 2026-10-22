"""Read one real campaign directory end to end and report what the reader produced.

    python probe_measured.py <condition dir> [channel numbers ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from velch.io.measured import CAMPAIGN_CHANNELS, campaign_plan, read_channel

folder = Path(sys.argv[1])
wanted = [int(value) for value in sys.argv[2:]] or [1, 8, 9, 10, 13, 15]
plan = campaign_plan(unit_system="raw")
by_channel = {item.channel: item for item in CAMPAIGN_CHANNELS}
print(f"folder  : {folder}")
for channel in wanted:
    spec = by_channel.get(channel)
    try:
        time_s, values = read_channel(folder, channel)
    except Exception as error:  # noqa: BLE001 - probe, report and continue
        print(f"CH{channel:02d}    error: {type(error).__name__}: {error}")
        continue
    dt = float(np.median(np.diff(time_s)))
    label = f"{spec.name}/{spec.unit}" if spec else "?"
    print(f"CH{channel:02d} {label:<10} n={values.size:<8} dt={dt * 1e3:6.3f} ms "
          f"t={time_s[0]:.3f}..{time_s[-1]:.3f} s "
          f"min={values.min():9.4f} max={values.max():9.4f} "
          f"span={values.max() - values.min():9.4f}")
