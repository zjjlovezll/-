"""Measure the real in-run share of profile sampling and contact search.

The micro-benchmarks time isolated calls; this wraps the two functions the
solver actually calls and reports accumulated wall time for a real run, so the
saving from a change can be projected without guesswork.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import velch.vehicle_solver as solver
from velch.profiles import ProfileSeries
from velch.vehicle import load_vehicle_case

BASE = Path("validation/crh380a_m")
CASE = BASE / "case_bench_0.json"

stats = {"sample_calls": 0, "sample_s": 0.0, "contact_calls": 0, "contact_s": 0.0, "misses": 0}
original_sample = ProfileSeries.sample
original_contact = solver.find_graph_contact


def timed_sample(self, s_m, direction=1):
    started = time.perf_counter()
    out = original_sample(self, s_m, direction)
    stats["sample_s"] += time.perf_counter() - started
    stats["sample_calls"] += 1
    return out


def timed_contact(*args, **kwargs):
    started = time.perf_counter()
    out = original_contact(*args, **kwargs)
    stats["contact_s"] += time.perf_counter() - started
    stats["contact_calls"] += 1
    return out


def main() -> None:
    ProfileSeries.sample = timed_sample
    solver.find_graph_contact = timed_contact

    case = load_vehicle_case(CASE)
    started = time.perf_counter()
    result = solver.simulate_vehicle(case)
    wall = time.perf_counter() - started

    nfev = result.summary["solver"]["nfev"]
    total_fun = stats["sample_s"] + stats["contact_s"]
    print(f"wall time                 : {wall:8.2f} s")
    print(f"nfev                      : {nfev}")
    print()
    print(f"ProfileSeries.sample      : {stats['sample_s']:7.2f} s  "
          f"({stats['sample_calls']:7d} calls, {stats['sample_s'] / stats['sample_calls'] * 1e6:6.1f} us each, "
          f"{100 * stats['sample_s'] / wall:4.1f}% of wall)")
    print(f"find_graph_contact        : {stats['contact_s']:7.2f} s  "
          f"({stats['contact_calls']:7d} calls, {stats['contact_s'] / stats['contact_calls'] * 1e6:6.1f} us each, "
          f"{100 * stats['contact_s'] / wall:4.1f}% of wall)")
    print(f"contact + sampling        : {total_fun:7.2f} s  ({100 * total_fun / wall:4.1f}% of wall)")
    print(f"remainder (connectors etc): {wall - total_fun:7.2f} s  ({100 * (wall - total_fun) / wall:4.1f}% of wall)")
    print()
    print(f"patches per RHS           : {stats['contact_calls'] / nfev:.2f}")
    print(f"per-RHS total             : {wall / nfev * 1e6:8.1f} us")
    print(f"per-RHS contact+sampling  : {total_fun / nfev * 1e6:8.1f} us")
    print(f"per-RHS connector+glue    : {(wall - total_fun) / nfev * 1e6:8.1f} us")
    (BASE / "profile_run_stats.json").write_text(
        json.dumps({**stats, "wall_s": wall, "nfev": nfev}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
