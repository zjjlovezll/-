import numpy as np, sys
sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\src")
from velch.vehicle import load_vehicle_case
case = load_vehicle_case(r"F:\ai道岔状态反演辨识\Velch\validation\crh380a_m\case_C_frog.json")
rail = [r for r in case.rails if r.id.endswith("right")][0]
print("stations:", len(rail.profiles.sample(80.0,1).profile.y_m))
ys = (738.0, 742.0, 746.0, 750.0, 755.0, 776.0)
print("   s(m)  " + "  ".join(f"y{y:.0f}" for y in ys))
for s in (79.968, 80.05, 80.20, 80.35, 80.50, 80.70, 81.00, 81.30, 81.70, 82.37):
    smp = rail.profiles.sample(s, 1)
    ry = np.asarray(smp.profile.y_m); rz = np.asarray(smp.profile.z_m)
    row = [f"{s:7.3f}"]
    for yabs in ys:
        iy = int(np.argmin(np.abs(ry - yabs*1e-3)))
        row.append(f"{rz[iy]*1e3:6.2f}")
    print("  ".join(f"{c:>7s}" for c in row), f"  [y range {ry.min()*1e3:.1f}..{ry.max()*1e3:.1f}, idx hits {[int(np.argmin(np.abs(ry-y*1e-3))) for y in ys]}]")
