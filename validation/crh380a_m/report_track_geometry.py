"""Report the rail-top geometry of the CRH380A_M turnout catalog.

For every referenced station the crown height (max z of the sampled profile) and
its lateral position are printed, together with the step size across the ten
duplicate-mileage pairs. This is the geometry the vehicle actually sees, so it
separates a genuine turnout relief from a bookkeeping error in the case.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
VEH = HERE.parents[1]
sys.path.insert(0, str(VEH / "src"))

from velch.profiles import load_profile  # noqa: E402

CATALOG = VEH / "diagnostics" / "crh380a_m_track_catalog.json"
RAIL_LATERAL_DISTANCE_M = 0.753


def rail(path: str, sign: int):
    return load_profile(Path(path), file_format="prr", surface="rail_top",
                        y_sign=sign, y_offset_m=sign * RAIL_LATERAL_DISTANCE_M, z_sign=-1)


def main() -> int:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    right = sorted([r for r in cat["profile_references"] if r["side"] == "right"], key=lambda r: r["index"])
    left = sorted([r for r in cat["profile_references"] if r["side"] == "left"], key=lambda r: r["index"])
    print(f"right stations {len(right)}  left stations {len(left)}")
    print()

    crowns = []
    for ref in right:
        g = rail(ref["path"], 1)
        k = int(np.argmax(g.z_m))
        crowns.append((float(ref["station_m"]), g.z_m[k], g.y_m[k], ref["path"]))
    heights = [c[1] for c in crowns]
    print("right rail crown height statistics")
    print(f"  min {min(heights)*1e3:+.4f} mm  max {max(heights)*1e3:+.4f} mm  "
          f"peak-to-peak {(max(heights)-min(heights))*1e3:.4f} mm")
    print()
    print("  station      crown z (mm)   crown y (mm)   d z vs previous (mm)   profile")
    prev = None
    for s, z, y, path in crowns:
        dz = "" if prev is None else f"{(z-prev)*1e3:+8.4f}"
        print(f"  {s:9.4f}   {z*1e3:+11.4f}   {y*1e3:+11.4f}   {dz:>12s}   {Path(path).name}")
        prev = z
    print()

    print("duplicate-mileage pairs: step from index i to i+1")
    for pair in cat["coincident_stations"]:
        i, j = pair["indices"]
        zi, zj = crowns[i][1], crowns[j][1]
        print(f"  s={pair['station_m']:9.4f}  i={i:3d} {Path(crowns[i][3]).name:32s} z {zi*1e3:+8.4f} mm   "
              f"j={j:3d} {Path(crowns[j][3]).name:32s} z {zj*1e3:+8.4f} mm   dz {(zj-zi)*1e3:+8.4f} mm")
    print()

    print("left rail stations")
    for ref in left:
        g = rail(ref["path"], -1)
        k = int(np.argmax(g.z_m))
        print(f"  s={float(ref['station_m']):9.4f}  crown z {g.z_m[k]*1e3:+8.4f} mm  "
              f"crown y {g.y_m[k]*1e3:+8.4f} mm  {Path(ref['path']).name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
