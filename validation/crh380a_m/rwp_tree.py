import h5py, sys
p = r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\results\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat"
f = h5py.File(p, "r")
found = []
def visit(name, obj):
    if isinstance(obj, h5py.Group) and "SRS_RWP" in name:
        found.append((name, len(obj)))
f.visititems(visit)
for n, k in sorted(found):
    print(f"{k:3d}  {n}")
