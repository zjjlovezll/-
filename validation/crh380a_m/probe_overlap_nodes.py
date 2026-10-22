"""How much of the rail profile actually lies inside the contact search window?

The planned pre-slice (crop the rail to a +-100 mm band around the wheel centre)
only helps if a large share of the rail nodes sits OUTSIDE ``[lower, upper]``.
If they are already inside, cropping cannot be done without changing the search
space, and the only sound speedup is resampling the profile itself.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

BASE = Path(r"F:\ai道岔状态反演辨识\Velch\validation\crh380a_m")
sys.path.insert(0, str(BASE.parent.parent / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402


def main() -> int:
    case = load_vehicle_case(BASE / "case_frog_N_strip05.json")
    dyn = case.dynamics
    q = np.zeros(case.vehicle.state_size, dtype=float)
    v = np.zeros_like(q)
    force, geometry = dyn.evaluate(0.0, q, v)

    print(f"contacts: {len(geometry)}")
    for name, resp in sorted(geometry.items()):
        if resp.geometry is None:
            print(f"{name:>22}: no geometry")
            continue
        g = resp.geometry
        print(
            f"{name:>22}: y={g.y_m * 1e3:8.3f} mm "
            f"pen={g.penetration_m * 1e6:8.3f} um "
            f"slope={np.degrees(np.arctan(g.normal_y / max(1e-12, g.normal_z))):7.2f} deg "
            f"edge={g.edge_limited}"
        )

    # Inspect the raw profile arrays the contact search sees.
    for template in case.track.rail_templates:
        prof = template.profile
        wheels = template.wheel_profile
        print(f"\ntemplate {template.template_id}")
        print(f"  rail   y: {prof.y_m.size:5d} nodes "
              f"[{prof.y_m.min() * 1e3:.3f}, {prof.y_m.max() * 1e3:.3f}] mm "
              f"span {(prof.y_m.max() - prof.y_m.min()) * 1e3:.3f} mm")
        print(f"  wheel  y: {wheels.y_m.size:5d} nodes "
              f"[{wheels.y_m.min() * 1e3:.3f}, {wheels.y_m.max() * 1e3:.3f}] mm "
              f"span {(wheels.y_m.max() - wheels.y_m.min()) * 1e3:.3f} mm")
        break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
