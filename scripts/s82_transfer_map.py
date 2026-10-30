"""Which of SDITT's three lines owns the wheel, as a function of mileage -- from crown heights alone.

This is the forward half of the lowering inversion: before running anything, the geometry already says
where the wheel must transfer between the stock rail, the switch blade and the point rail.  If the
transfer mileages measured on a zero-irregularity run agree with this map, the chain is sound; if they do
not, either a lateral datum or the contact search is wrong.

Reads the three tables through `s81_sditt_lines`, so there is one implementation of the table parsing.

Run: PYTHONPATH=src python -X utf8 scripts/s82_transfer_map.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent


def _s81():
    spec = importlib.util.spec_from_file_location("s81_lines", SCRIPT_DIR / "s81_sditt_lines.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["s81_lines"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    s81 = _s81()
    index = s81.section_index()
    lines: dict[str, list] = {}
    for name, table in s81.TABLES:
        rows = s81.read_table(s81.TABLE_DIR / table, index)
        unique: dict[float, object] = {}
        for row in rows:
            unique.setdefault(round(row.station_m, 6), row)
        lines[name] = sorted(unique.values(), key=lambda r: r.station_m)
        print(f"{name:9s} {len(lines[name]):4d} unique stations  "
              f"{lines[name][0].station_m:8.3f} .. {lines[name][-1].station_m:9.3f} m")

    cache: dict[Path, float] = {}

    def crown_of(section: Path) -> float:
        if section not in cache:
            cache[section] = s81.crown_m(section) * 1e3
        return cache[section]

    def crown_at(name: str, x: float) -> float | None:
        rows = lines[name]
        stations = np.array([row.station_m for row in rows])
        if x < stations[0] or x > stations[-1]:
            return None
        hi = int(np.searchsorted(stations, x))
        lo = max(hi - 1, 0)
        hi = min(hi, stations.size - 1)
        if hi == lo:
            return crown_of(rows[lo].section)
        weight = (x - stations[lo]) / (stations[hi] - stations[lo])
        return (1 - weight) * crown_of(rows[lo].section) + weight * crown_of(rows[hi].section)

    print("\n x(m)   deepest line   crowns present (mm; lower is higher up)")
    previous = ""
    owner: list[tuple[float, str]] = []
    for x in np.arange(45.0, 125.001, 0.25):
        present = {name: crown_at(name, float(x)) for name in lines}
        present = {name: value for name, value in present.items() if value is not None}
        deepest = min(present, key=present.get)
        if deepest != previous:
            owner.append((round(float(x), 2), deepest))
            print(f"{x:7.2f}   {deepest:12s}   " + ", ".join(f"{k} {v:+.2f}" for k, v in present.items()))
            previous = deepest

    print("\nload-transfer map:")
    bounds = [item[0] for item in owner] + [125.01]
    for i, (start, name) in enumerate(owner[:-1]):
        end = bounds[i + 1]
        if end - start < 0.5:  # ties within 0.02 mm: both lines are level, contact decides
            continue
        print(f"  {start:7.2f} .. {end:7.2f} m   {name}")
    print("\nTies shorter than 0.5 m are omitted: there both crowns sit within 0.02 mm, so which body")
    print("carries is decided by the wheel's lateral position inside the contact search, not by height.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
