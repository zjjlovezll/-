"""Dump the mileage grid Simpack binds its rail profiles to.

`rail.r.prof.file (k, $RWR_Rail_1) = '...prr'` and
`rail.r.prof.s (k, $RWR_Rail_1) = <mileage>` are two indexed arrays. Their
values are the *only* places the model says which cross-section applies where,
so any Velch case must reproduce this grid exactly. A denser or coarser grid
changes the interpolated running surface.

Usage: python probe_spck_profile_index.py <spck> [lo_m hi_m]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PROFILE = re.compile(
    r"rail\.r\.prof\.s\s*\(\s*(\d+)\s*,\s*(\$?\w+)\s*\)\s*=\s*([-\d.eE+]+)"
    r"|rail\.r\.prof\.file\s*\(\s*(\d+)\s*,\s*(\$?\w+)\s*\)\s*=\s*'([^']+)'")
SETTING = re.compile(r"(?m)^\s*(rw\.cont\.[\w.]+|rwpair\.cont\.[\w.]+|cont\.[\w.]+|"
                     r"fn\.[\w.]+|ft\.[\w.]+|fric\.[\w.]+|wheel\.state)\s*=\s*([^\s!]+)")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    text = Path(argv[1]).read_text(encoding="utf-8", errors="replace")
    lo = float(argv[2]) if len(argv) > 2 else 78.0
    hi = float(argv[3]) if len(argv) > 3 else 82.0
    positions: dict[int, float] = {}
    files: dict[int, str] = {}
    for match in PROFILE.finditer(text):
        if match.group(1):
            positions[int(match.group(1))] = float(match.group(3))
        else:
            files[int(match.group(4))] = match.group(6)
    print(f"bound profiles: {len(positions)} positions, {len(files)} files")
    ordered = sorted(positions.items())
    values = [v for _, v in ordered]
    steps = [b - a for a, b in zip(values, values[1:])]
    if steps:
        print(f"mileage range {values[0]:.4f} .. {values[-1]:.4f} m")
        print(f"step: min {min(steps):.6f}  median {sorted(steps)[len(steps) // 2]:.6f} "
              f" max {max(steps):.6f}  (n={len(steps)})")
        dense = [(k, v, s) for (k, v), s in zip(ordered, [0.0] + steps) if s < 0.2]
        print(f"steps < 0.2 m: {len(dense)}")
    print(f"\nwindow {lo}-{hi} m:")
    print(f"  {'k':>3s} {'s_m':>10s} {'step_mm':>9s}  file")
    previous = None
    for key, value in ordered:
        if not (lo <= value <= hi):
            continue
        step = "" if previous is None else f"{(value - previous) * 1e3:9.2f}"
        print(f"  {key:3d} {value:10.4f} {step:>9s}  {files.get(key, '?')}")
        previous = value
    print("\ncontact / friction settings found in this file:")
    for match in SETTING.finditer(text):
        print(f"  {match.group(1)} = {match.group(2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
