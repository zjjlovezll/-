"""Read the rail profile Simpack's contact actually used, per timestep.

``timeInt/railWheelPair/<pair>/Rail/Profile_y|Profile_z`` store, for every output
step, the contact-relevant nodes of the rail profile (a short array behind an
HDF5 reference). That is Simpack's own answer to "what surface is under this
wheel here", so it settles any dispute about interpolation, discretisation or
which of two coincident sections is active.

Node coordinates are rail-local metres; add the rail's lateral offset
(0.753 m for this model's right rail) to compare with the case files.

Usage: python probe_simpack_rail_profile.py <350.mat> <x_m> [<x_m> ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

import h5py
import numpy as np

V = 97.2222222222
X0 = 23.5
BAND = (0.736, 0.790)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    path = Path(argv[1])
    targets = [float(v) for v in argv[2:]]
    with h5py.File(path, "r") as handle:
        for side in ("L", "R"):
            base = f"timeInt/railWheelPair/SS_F__S_WS_F__RWP_{side}/Rail"
            ys = np.asarray(handle[f"{base}/Profile_y/values"]).reshape(-1)
            zs = np.asarray(handle[f"{base}/Profile_z/values"]).reshape(-1)
            times = np.linspace(0.0, 1.2, ys.size)
            offset = 0.753 if side == "R" else -0.753
            print(f"=== RWP_{side} ({ys.size} steps, lateral offset {offset:+.3f} m)")
            print(f"  {'x_m':>7s} {'nodes':>5s} {'y_span_mm':>15s} {'z_min':>8s} "
                  f"{'z_max':>8s} {'crown_y':>8s} {'band_max':>9s} {'band_y':>8s}")
            for target in targets:
                index = int(np.argmin(np.abs(times - (target - X0) / V)))
                y = np.asarray(handle[ys[index]]).reshape(-1).astype(float)
                z = np.asarray(handle[zs[index]]).reshape(-1).astype(float)
                y_abs = y + offset
                crown = int(np.argmax(z))
                mask = (y_abs >= BAND[0]) & (y_abs <= BAND[1])
                band_max = z[mask].max() if mask.any() else float("nan")
                band_y = y_abs[mask][int(np.argmax(z[mask]))] if mask.any() else float("nan")
                print(f"  {target:7.3f} {y.size:5d} {y_abs.min() * 1e3:7.1f}..{y_abs.max() * 1e3:7.1f} "
                      f"{z.min() * 1e3:8.3f} {z.max() * 1e3:8.3f} {y_abs[crown] * 1e3:8.1f} "
                      f"{band_max * 1e3:9.3f} {band_y * 1e3:8.1f}")
                if target == targets[0]:
                    print("     nodes (y_abs mm -> z mm):")
                    for yi, zi in zip(y_abs * 1e3, z * 1e3):
                        print(f"       {yi:9.2f} {zi:9.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
