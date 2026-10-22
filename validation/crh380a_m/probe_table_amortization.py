# -*- coding: utf-8 -*-
"""B3: is a per-(station, roll) contact table worth building for an inversion batch?

A single forward run visits each station only a few times, so building a table for
it does not pay (measured earlier: 1:40).  An inversion batch re-visits the same
stations once per parameter set, so the table is amortised over N runs.  This
probe measures the *actual* reuse pattern of one run by instrumenting the contact
call, then prices the batch with the measured unit costs:

    direct : 154.2 us per contact search   (measured, bench_contact_parts.py)
    table  :   8.46 us per lookup, 23 ms to build one (station, roll) cell
"""
import collections
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE / (sys.argv[1] if len(sys.argv) > 1 else "case_frog_N_strip05.json")
OUT = HERE / f"out_b3_{CASE.stem}"

DIRECT_US = 154.2
MAP_US = 8.46
BUILD_S = 0.023

counts: collections.Counter = collections.Counter()
originals: dict[str, object] = {}


def install() -> None:
    import velch.contact as contact
    import velch.vehicle_solver as solver

    for module in (contact, solver):
        original = getattr(module, "find_strip_contact", None)
        if original is None:
            continue
        originals[module.__name__] = original

        def wrapper(wheel_profile, rail_sample, *args, _orig=original, **kwargs):
            key = (round(float(rail_sample.lower_s_m), 4),
                   round(float(rail_sample.upper_s_m), 4),
                   round(float(kwargs.get("wheel_roll_rad", 0.0)), 4))
            counts[key] += 1
            return _orig(wheel_profile, rail_sample, *args, **kwargs)

        setattr(module, "find_strip_contact", wrapper)


def main() -> int:
    install()
    from velch.cli import main as cli_main

    sys.argv = ["velch", "run-vehicle", str(CASE), "--output", str(OUT)]
    began = time.perf_counter()
    code = cli_main()
    elapsed = time.perf_counter() - began
    if code not in (0, None):
        raise SystemExit(f"run failed with {code}")

    total = sum(counts.values())
    distinct = len(counts)
    reuse = total / distinct if distinct else 0.0

    rows = []
    for runs in (1, 5, 10, 20, 50):
        direct = runs * total * DIRECT_US * 1e-6
        table = distinct * BUILD_S + runs * total * MAP_US * 1e-6
        rows.append({"runs": runs, "direct_s": direct, "table_s": table,
                     "speedup": direct / table if table else float("inf")})

    payload = {
        "case": CASE.name,
        "wall_clock_s": elapsed,
        "contact_calls": total,
        "distinct_cells": distinct,
        "reuse_per_cell": reuse,
        "unit_costs": {"direct_us": DIRECT_US, "map_us": MAP_US, "build_s": BUILD_S},
        "batch": rows,
        "histogram_top": counts.most_common(5),
        "keys": sorted(f"{k[0]:.4f}|{k[1]:.4f}|{k[2]:.4f}" for k in counts),
    }
    (HERE / f"b3_amortization_{CASE.stem}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wall {elapsed:.1f} s   calls {total}   distinct cells {distinct}   "
          f"reuse/cell {reuse:.2f}")
    print(f"{'runs':>5s} {'direct s':>10s} {'table s':>10s} {'speedup':>8s}")
    for row in rows:
        print(f"{row['runs']:5d} {row['direct_s']:10.2f} {row['table_s']:10.2f} "
              f"{row['speedup']:8.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
