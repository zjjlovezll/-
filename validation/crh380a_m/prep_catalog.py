"""Turnout body catalog v1: zones, per-body kinematics, fused-section detection.

Reads turnout_bodies_raw.json (from prep_bodies.py) and answers three questions:
  1. where the turnout geometry actually starts and ends,
  2. what each tracked rail body does along the mileage (drift / rise / width),
  3. which sections are *fused* (two bodies merged into one ridge) and therefore
     cannot be fixed by lateral smoothing at all.
"""
import json
from pathlib import Path

import numpy as np

BASE = Path(r"F:\ai道岔状态反演辨识\Velch\validation\crh380a_m")
raw = json.loads((BASE / "turnout_bodies_raw.json").read_text(encoding="utf-8"))
stations = raw["stations"]
s = np.array([st["s_m"] for st in stations])

print(f"stations {len(stations)}  s {s[0]:.3f} .. {s[-1]:.3f}")
n = np.array([st["n_bodies"] for st in stations])
print(f"bodies/station: min {n.min()} max {n.max()}   multi-body stations {int((n > 1).sum())}")

# ---- zone 1: extent of fused cross-sections -------------------------------
multi = s[n > 1]
print(f"\nmulti-body zone: {multi.min():.3f} .. {multi.max():.3f} m "
      f"({len(multi)} stations)")
gaps = np.diff(multi)
big = np.where(gaps > 0.5)[0]
print("  internal gaps > 0.5 m:", [(round(float(multi[i]), 3), round(float(multi[i + 1]), 3))
                                  for i in big])
# cluster into contiguous zones
zones, start = [], 0
for i in big:
    zones.append((multi[start], multi[i]))
    start = i + 1
zones.append((multi[start], multi[-1]))
print(f"  zones ({len(zones)}):", [(round(float(a), 3), round(float(b), 3)) for a, b in zones])

# ---- zone 2: per-body kinematics -----------------------------------------
print("\n=== tracks ===")
print(f"{'id':>4} {'n':>4} {'s_first':>8} {'s_last':>8} {'y0':>7} {'y1':>7} "
      f"{'dy/ds':>7} {'z0':>7} {'z1':>7} {'dz/ds':>7} {'w0':>6} {'w1':>6}")
rows = []
for t in raw["tracks"]:
    if len(t["samples"]) < 3:
        continue
    ss = np.array([stations[k]["s_m"] for _, k in t["samples"]])
    bs = [stations[a]["bodies"][b] for a, b in t["samples"]]
    cy = np.array([x["crown_y_m"] for x in bs])
    cz = np.array([x["crown_z_m"] for x in bs])
    wd = np.array([x["width_m"] for x in bs])
    dy = (cy[-1] - cy[0]) / max(ss[-1] - ss[0], 1e-9) * 1e3
    dz = (cz[-1] - cz[0]) / max(ss[-1] - ss[0], 1e-9) * 1e3
    rows.append(dict(id=t["id"], n=len(ss), s0=float(ss[0]), s1=float(ss[-1]),
                     y0=float(cy[0]), y1=float(cy[-1]), dy=dy, z0=float(cz[0]),
                     z1=float(cz[-1]), dz=dz, w0=float(wd[0]), w1=float(wd[-1]),
                     cy=cy, cz=cz, wd=wd, ss=ss))
    print(f"{t['id']:>4} {len(ss):>4} {ss[0]:>8.3f} {ss[-1]:>8.3f} {cy[0]*1e3:>7.1f} "
          f"{cy[-1]*1e3:>7.1f} {dy:>7.2f} {cz[0]*1e3:>7.2f} {cz[-1]*1e3:>7.2f} "
          f"{dz:>7.2f} {wd[0]*1e3:>6.1f} {wd[-1]*1e3:>6.1f}")
print("  (dy/ds, dz/ds in mm per metre)")

# ---- fusion detection: wide single ridge inside a multi-body zone --------
print("\n=== fused candidates (single ridge wider than a plain head) ===")
plain_width = np.median([st["bodies"][0]["width_m"] for st in stations if st["n_bodies"] == 1])
print(f"  plain head width = {plain_width*1e3:.1f} mm")
fused = []
for st in stations:
    if st["n_bodies"] == 1 and st["bodies"][0]["width_m"] > plain_width * 1.25:
        lo = st["bodies"][0]["y_lo_m"] * 1e3
        hi = st["bodies"][0]["y_hi_m"] * 1e3
        fused.append((st["s_m"], lo, hi, st["bodies"][0]["width_m"] * 1e3))
print(f"  {len(fused)} stations:")
for f in fused:
    print(f"    s={f[0]:7.3f}  y=[{f[1]:6.1f},{f[2]:6.1f}]  w={f[3]:5.1f} mm")
