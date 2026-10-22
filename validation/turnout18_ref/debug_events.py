"""Debug the three failing event-descriptor expectations."""

from __future__ import annotations

import numpy as np

from velch.inverse.events import describe_event

time = np.linspace(0.0, 1.0, 512)
width = 0.05
values = -np.exp(-0.5 * ((time - 0.5) / width) ** 2)
print("gaussian:", describe_event(time, values).report())

time2 = np.linspace(0.0, 4.0, 2048)
values2 = -np.exp(-time2 / 10.0)
print("exponential window 0.25:", describe_event(time2, values2, window_s=0.25).report())

time3 = np.linspace(0.0, 1.0, 1024)
values3 = np.sin(2.0 * np.pi * 20.0 * time3) * np.exp(-3.0 * time3)
print("oscillation:", describe_event(time3, values3, index=13).report())
