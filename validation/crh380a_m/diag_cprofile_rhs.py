"""cProfile one RHS loop and print the hottest entries.

Unlike the wall-clock split (``profile_rhs_parts.py``) this attributes cost to the
Python frame that issues each numpy call, which is what locates a hot spot *inside*
a function rather than only at its call site.
"""

from __future__ import annotations

import cProfile
import pstats
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from velch import vehicle_solver as vs_module        # noqa: E402
from velch.vehicle import load_vehicle_case          # noqa: E402


def main() -> int:
    case = load_vehicle_case(Path(sys.argv[1]))
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    dynamics = vs_module.VehicleDynamics(case)
    q = np.asarray(case.initial_q, float)
    v = np.asarray(case.initial_v, float)
    try:
        dynamics.evaluate(0.0, q, v)
        profile = cProfile.Profile()
        profile.enable()
        for _ in range(repeats):
            dynamics.evaluate(0.0, q, v)
        profile.disable()
    finally:
        dynamics.close()

    stats = pstats.Stats(profile)
    stats.sort_stats("tottime")
    print(f"case {case.case_id}   RHS calls {repeats}")
    stats.print_stats(18)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
