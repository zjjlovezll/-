"""Compare the closed-form quadratic against ``np.polyfit`` on real contact windows."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from velch.contact_law import quadratic_fit  # noqa: E402

rng = np.random.default_rng(20261020)
worst = 0.0
for trial in range(200):
    count = int(rng.integers(5, 80))
    span = float(rng.uniform(5e-4, 1.2e-2))
    t = np.sort(rng.uniform(-span, span, count))
    z = 0.3 - 2.1 * t + 850.0 * t * t + rng.normal(0.0, 1e-7, count)
    reference = np.polyfit(t, z, 2)
    mine = quadratic_fit(t, z)
    error = float(np.max(np.abs(reference - mine)))
    worst = max(worst, error)
    if trial < 3:
        print(f"n={count:3d} span={span:.3e}  polyfit={reference}  closed={mine}")
print(f"worst |closed - polyfit| over 200 windows: {worst:.3e}")

t = np.linspace(-1e-3, 1e-3, 41)
z = 1e-3 * (1.0 - (t / 1e-3) ** 2)
a = np.polyfit(t, z, 2)
b = quadratic_fit(t, z)
print(f"parabola curvature: polyfit {2 * a[0]:.6f}  closed {2 * b[0]:.6f}  expected {-2e-3 / 1e-6:.6f}")
