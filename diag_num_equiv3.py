import sys, numpy as np
sys.path.insert(0,"src")
from velch.contact import _grid_slope
print("numpy", np.__version__)
x = np.array([-0.7175387543,-0.7166985491,-0.7120247941,-0.7118994177,-0.7081098279])
z = np.array([-0.0190384755,-0.0189887890,-0.0170805720,-0.0181194986,-0.0196769607])
ref = np.empty_like(z)
ref[1:-1] = (z[2:]-z[:-2])/(x[2:]-x[:-2])
ref[0] = (z[1]-z[0])/(x[1]-x[0]); ref[-1] = (z[-1]-z[-2])/(x[-1]-x[-2])
print("textbook", ref)
print("np.grad ", np.gradient(z, x, edge_order=1))
print("mine    ", _grid_slope(z, x))
print("np.grad dx=", np.gradient(z, np.diff(x), edge_order=1))
print("simple  ", np.gradient(np.array([0.,1.,4.,9.]), np.array([0.,1.,2.,3.])))
