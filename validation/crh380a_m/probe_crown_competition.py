"""Why does the per-body crown datum break the frog band? Show the competing crowns."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

CASE = BASE / "validation" / "crh380a_m" / "case_I_wing.json"


def main() -> int:
    from velch.vehicle import load_vehicle_case

    print(f"case {CASE.name}")
    loaded = load_vehicle_case(CASE)
    for rail in loaded.rails:
        print(f"  rail y_offset {rail.y_offset_m:+.3f}  bodies {len(rail.bodies)}")
        for body in rail.bodies:
            limit = -1.0 if body.s_hi_m == float("inf") else body.s_hi_m
            print(f"     {body.id:>8} s {body.s_lo_m:.2f}..{limit:.2f}  "
                  f"window {body.y_window_m}")
    rail = [item for item in loaded.rails if item.y_offset_m > 0][0]
    for target_s in (40.0, 79.5, 80.0, 80.34, 80.5, 88.0):
        print(f"\n--- station {target_s:.3f} m")
        for body in rail.bodies:
            if not body.covers(target_s):
                continue
            sample = body.sample(target_s)
            ys = np.asarray(sample.profile.y_m, dtype=float)
            zs = np.asarray(sample.profile.z_m, dtype=float)
            order = np.argsort(zs)[-3:][::-1]
            tops = ", ".join(f"(y={ys[k] * 1e3:7.2f} z={zs[k] * 1e3:+8.3f})"
                             for k in order)
            crown_y = float(ys[int(np.argmax(zs))])
            print(f"  {body.id:>8}: n={ys.size:5d} crown_y={crown_y * 1e3:7.2f} "
                  f"crown_z={zs.max() * 1e3:+8.3f}  top3 {tops}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
