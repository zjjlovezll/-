"""Read Simpack's own contact-point coordinates at the frog.

`SS_F__S_WS_F__F_RWContact_RWP_L|R` is a force element that records, besides the
force, the contact point `x`/`y`/`z` and a 3-component `abs`. Those are the
coordinates Simpack itself resolved for the contact, so they answer the question
"which rail surface did Simpack actually press the wheel on at 79-81 m". Our
solver only reports its own contact geometry; this is the independent check.

Front axle starts at x = 23.5 m and runs at 97.222 m/s, so the wall-clock time
of a mileage x is (x - 23.5) / 97.222 s.

Usage: python probe_simpack_contact_point.py <350.mat> [x1 x2 ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

import h5py
import numpy as np

V = 97.2222222222
X0 = 23.5
BASE = "timeInt/forceForce"


def channel(handle, path: str) -> np.ndarray:
    return np.asarray(handle[path]["values"]).reshape(-1)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = Path(argv[1])
    targets = [float(v) for v in argv[2:]] or [79.452, 79.938, 80.278, 80.424, 80.910, 82.368]
    with h5py.File(path, "r") as handle:
        for side in ("L", "R"):
            base = f"{BASE}/SS_F__S_WS_F__F_RWContact_RWP_{side}"
            names = [n.decode() if isinstance(n, bytes) else str(n)
                     for n in np.asarray(handle[f"{base}/name"]).reshape(-1)]
            units_node = handle[f"{base}"].get("unit")
            units = ([] if units_node is None else
                     [u.decode() if isinstance(u, bytes) else str(u)
                      for u in np.asarray(units_node).reshape(-1)])
            print(f"=== RWP_{side}: {len(names)} channels")
            for index, name in enumerate(names):
                unit = units[index] if index < len(units) else ""
                print(f"    {name:38s} [{unit}]")
            time = channel(handle, f"{BASE}/SS_F__S_WS_F__F_RWContact_RWP_{side}/x")
            y = channel(handle, f"{BASE}/SS_F__S_WS_F__F_RWContact_RWP_{side}/y")
            z = channel(handle, f"{BASE}/SS_F__S_WS_F__F_RWContact_RWP_{side}/z")
            fz = channel(handle, f"{base}/z")
            t = np.linspace(0.0, 1.2, time.size)
            print(f"    t range {t[0]:.4f}..{t[-1]:.4f} s, n={t.size}")
            print(f"    {'x_target':>9s} {'t_s':>8s} {'contact x':>11s} {'contact y':>11s} "
                  f"{'contact z':>11s} {'force z':>11s}")
            for target in targets:
                tt = (target - X0) / V
                index = int(np.argmin(np.abs(t - tt)))
                print(f"    {target:9.3f} {t[index]:8.4f} {time[index]:11.5f} {y[index]:11.5f} "
                      f"{z[index]:11.6f} {fz[index]:11.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
