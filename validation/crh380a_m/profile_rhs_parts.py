"""Attribute one RHS evaluation to its parts on a real frozen state.

Patches ``find_graph_contact``, ``evaluate_contact`` and ``ProfileSeries.sample`` at
their call sites in ``vehicle_solver`` so the right-hand-side cost is split into
geometry, contact force law and profile sampling, then calls the vehicle RHS many
times at one fixed state.  Wall-clock shares, not a sampling profile, so no
instrumentation overhead distorts the split.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from velch import profiles as profiles_module        # noqa: E402
from velch import vehicle_solver as vs_module        # noqa: E402
from velch.vehicle import load_vehicle_case          # noqa: E402

TIMERS: dict[str, float] = {}
COUNTS: dict[str, int] = {}
SAMPLES: list[tuple] = []


def _wrap(module, name, key):
    original = getattr(module, name)

    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            out = original(*args, **kwargs)
        finally:
            TIMERS[key] = TIMERS.get(key, 0.0) + (time.perf_counter() - start)
            COUNTS[key] = COUNTS.get(key, 0) + 1
        if key == "geometry" and len(SAMPLES) < 8:
            SAMPLES.append((kwargs.get("search_half_width_m"),
                            kwargs.get("previous_y_m"),
                            kwargs.get("normal_policy"),
                            None if out is None else round(out.penetration_m * 1e6, 3)))
        return out

    setattr(module, name, wrapper)


def main() -> int:
    case_path = Path(sys.argv[1])
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    case = load_vehicle_case(case_path)

    _wrap(vs_module, "find_graph_contact", "geometry")
    _wrap(vs_module, "evaluate_contact", "force")
    _wrap(profiles_module.ProfileSeries, "sample", "sample")

    dynamics = vs_module.VehicleDynamics(case)
    q = np.asarray(case.initial_q, float)
    v = np.asarray(case.initial_v, float)
    try:
        dynamics.evaluate(0.0, q, v)          # warm caches
        for key in list(TIMERS):
            TIMERS[key] = 0.0
            COUNTS[key] = 0
        start = time.perf_counter()
        for _ in range(repeats):
            dynamics.evaluate(0.0, q, v)
        total = time.perf_counter() - start
    finally:
        dynamics.close()

    per_rhs_us = total / repeats * 1e6
    print(f"case            : {case.case_id}")
    print(f"RHS calls       : {repeats}   dimension={dynamics.dimension}")
    print(f"per RHS         : {per_rhs_us:9.1f} us")
    print()
    print(f"{'part':<12}{'calls/RHS':>11}{'us/RHS':>10}{'share':>9}{'us/call':>10}")
    for key in ("geometry", "force", "sample"):
        calls = COUNTS.get(key, 0)
        spent = TIMERS.get(key, 0.0) / repeats * 1e6
        share = spent / per_rhs_us * 100.0
        per_call = spent / (calls / repeats) if calls else 0.0
        print(f"{key:<12}{calls / repeats:>11.2f}{spent:>10.2f}{share:>8.1f}%{per_call:>10.2f}")
    residual = per_rhs_us - sum(TIMERS.get(k, 0.0) for k in TIMERS) / repeats * 1e6
    print(f"{'remainder':<12}{'-':>11}{residual:>10.2f}{residual / per_rhs_us * 100:>8.1f}%")
    print()
    print("first geometry calls (half_width, previous_y, policy, pen_um):")
    for entry in SAMPLES:
        print(f"  {entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
