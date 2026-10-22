"""List the mileage ranges where the wing run loses right-rail contact."""

from __future__ import annotations

import csv
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def main() -> None:
    run = HERE / (sys.argv[1] if len(sys.argv) > 1 else "out_wing_frog_0p05s")
    with (run / "history.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    x = [float(r["axle1_x_m"]) for r in rows]
    fr = [float(r["axle1_right_normal_n"]) for r in rows]
    z = [float(r["axle1_z_m"]) for r in rows]
    pen = [float(r["axle1_right_penetration_m"]) for r in rows]

    runs = []
    start = None
    for i, v in enumerate(fr):
        if v < 1.0 and start is None:
            start = i
        elif v >= 1.0 and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(fr) - 1))

    print(f"run {run.name}: {len(rows)} samples, x {x[0]:.3f}..{x[-1]:.3f} m")
    print(f"right-rail force < 1 kN in {len(runs)} segment(s):")
    for a, b in runs:
        print(f"  x {x[a]:7.3f} .. {x[b]:7.3f} m   ({b - a + 1} samples)  z {z[a]*1e3:+.3f}..{z[b]*1e3:+.3f} mm")
    print()
    print("   x_m    F_R(kN)  pen_mm      z_mm")
    for i, xi in enumerate(x):
        if not (80.3 <= xi <= 82.2):
            continue
        print(f"  {xi:7.3f} {fr[i]/1e3:8.2f} {pen[i]*1e3:7.4f} {z[i]*1e3:8.3f}")


if __name__ == "__main__":
    main()
