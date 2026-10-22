"""Why did the full 1.2 s run get worse with the support compliance?

Prints the energy budget and where the contact is lost, so the quasi-static
compliance can be judged as a model rather than as a number.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np

BASE = pathlib.Path(__file__).resolve().parent
SPEED = 97.22222222222221


def inspect(directory: str) -> None:
    root = BASE / directory
    summary = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["summary"]
    history = np.genfromtxt(root / "history.csv", delimiter=",", names=True)
    force = history["axle1_right_normal_n"]
    z = history["axle1_z_m"]
    x = history["axle1_x_m"]
    lost = np.where(force <= 0.0)[0]
    print(f"== {directory}")
    print(f"   energy: initial {summary['initial_mechanical_energy_j']:.1f} J"
          f" -> final {summary['final_mechanical_energy_j']:.1f} J"
          f"  change {summary['energy_change_j']:+.1f} J")
    print(f"   nfev {summary['solver']['nfev']}  gates_ok {summary['result_status']}")
    print(f"   force: peak {force.max() / 1e3:.2f} kN, min {force.min() / 1e3:.3f} kN,"
          f" mean {force.mean() / 1e3:.3f} kN")
    print(f"   wheel z: peak-to-peak {np.ptp(z) * 1e3:.3f} mm,"
          f" min {z.min():.6f} m, max {z.max():.6f} m")
    if lost.size:
        groups = []
        start = previous = int(lost[0])
        for index in lost[1:]:
            if index != previous + 1:
                groups.append((start, previous))
                start = index
            previous = int(index)
        groups.append((start, previous))
        print(f"   contact lost in {lost.size} samples, {len(groups)} runs:")
        for first, last in groups:
            print(f"      x {x[first]:.3f}..{x[last]:.3f} m"
                  f" ({last - first + 1} samples)")
    else:
        print("   contact never lost")


for name in ("out_Y_base", "out_Y_support"):
    inspect(name)
