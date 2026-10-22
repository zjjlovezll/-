import sys, numpy as np
sys.path.insert(0,"src")
from velch.contact import _grid_slope
np.set_printoptions(precision=10, suppress=False, linewidth=160)
rng = np.random.default_rng(7)
n = rng.integers(3, 400)
x = np.cumsum(rng.uniform(1e-4, 5e-3, n)) - 1.0
z = np.cumsum(rng.normal(0, 1e-3, n))
a = _grid_slope(z, x); b = np.gradient(z, x, edge_order=1)
d = np.abs(a-b); i = int(np.argmax(d))
print("n", n, "worst idx", i, "of", n)
print("x  ", x[max(0,i-2):i+3])
print("z  ", z[max(0,i-2):i+3])
print("mine", a[max(0,i-2):i+3])
print("numpy", b[max(0,i-2):i+3])
print("manual interior", (z[i+1]-z[i-1])/(x[i+1]-x[i-1]) if 0<i<n-1 else "edge")
print("num diff count", int(np.sum(d>0)), "of", n)
