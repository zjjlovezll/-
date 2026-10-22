import sys, numpy as np, math
sys.path.insert(0,"src")
from velch.contact import _grid_slope, _merge_grid

rng = np.random.default_rng(7)
worst = 0.0
for trial in range(200):
    n = rng.integers(3, 400)
    x = np.cumsum(rng.uniform(1e-4, 5e-3, n)) - 1.0
    z = np.cumsum(rng.normal(0, 1e-3, n))
    a = _grid_slope(z, x)
    b = np.gradient(z, x, edge_order=1)
    worst = max(worst, float(np.max(np.abs(a - b))))
print("max |_grid_slope - np.gradient| =", worst)

# merged grid vs np.unique
worst2 = 0
for trial in range(200):
    a = np.sort(rng.uniform(-1, 1, 500)); b = np.sort(rng.uniform(-1, 1, 900))
    lo, hi = -0.9, 0.9
    ref = np.unique(np.concatenate((np.array([lo,hi]), a[(a>lo)&(a<hi)], b[(b>lo)&(b<hi)])))
    got = _merge_grid(a, b, lo, hi)
    worst2 = max(worst2, abs(ref.size-got.size))
    if ref.size == got.size and ref.size:
        worst2 = max(worst2, float(np.max(np.abs(ref-got))))
print("merged-grid size/value mismatch =", worst2)
