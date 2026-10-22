import sys
from pathlib import Path

MAT = Path(r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\results"
           r"\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat")
sys.path.insert(0, r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\src")

import h5py

with h5py.File(MAT, "r") as handle:
    names = []
    handle.visititems(lambda name, obj: names.append(name)
                      if isinstance(obj, h5py.Group) and "RWP" in name else None)
print("groups with RWP:", len(names))
for name in names[:12]:
    print("  ", name)
print("...")
for name in names:
    if name.endswith("R_Pair") or name.endswith("Pair"):
        print("PAIR:", name)
