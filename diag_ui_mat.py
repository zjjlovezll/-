"""Probe the Simpack 350.mat structure for the UI compare screen (read-only)."""
import h5py
import numpy as np

P = r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\results\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat"

f = h5py.File(P, "r")
t = f["timeInt"]


def decode(arr):
    flat = np.asarray(arr).ravel()
    return "".join(chr(int(c)) for c in flat if int(c) != 0)


print("name:", decode(t["name"][()]))
print("c_name:", decode(t["c_name"][()]))


def walk(g, prefix="", depth=0):
    if depth > 3:
        return
    for k in list(g.keys())[:12]:
        o = g[k]
        if isinstance(o, h5py.Group):
            print(f"{prefix}{k}/  (group, {len(o.keys())} children: {list(o.keys())[:6]})")
            walk(o, prefix + "  ", depth + 1)
        else:
            print(f"{prefix}{k}  {o.shape} {o.dtype}")


for key in ("time", "railWheelPair", "forceForce", "bodyPosTrans"):
    if key in t:
        print("=" * 20, key)
        o = t[key]
        if isinstance(o, h5py.Group):
            walk(o, "  ")
        else:
            print("  ", o.shape, o.dtype)
