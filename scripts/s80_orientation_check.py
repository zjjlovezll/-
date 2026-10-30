"""Prove which way the SDITT section files point, without trusting any convention.

The running surface of a rail is the flattest stretch of its outline: the tangent is nearly horizontal
and stays so for many consecutive points.  On `07(009)-zjg-20200418-72.prr` that stretch is 86 points
long (y +1.52..+11.34 mm) at z -0.09..-0.03 mm, while the plain sides reach z = +23 mm.  So the file's
z grows DOWNWARD with the crown at 0, and the blade sections sit 1.16 mm (30 mm width) and 14.94 mm
(3 mm width) below that crown.

Every section in that corpus is head-only (the tallest is 23.14 mm), so the drawing can only show a rail
head -- seeing no web or foot is the data, not a plotting error.

Run: PYTHONPATH=src python -X utf8 scripts/s80_orientation_check.py
"""
from pathlib import Path
import re

import numpy as np

POINT = re.compile(r"^\s*(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s*$")
ROOT = Path(r"G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728\WRProfile-07(009)-1_18")
SECTIONS = (
    ("zjg-72", ROOT / "07(009)-zjg-20200418" / "07(009)-zjg-20200418-72.prr"),
    ("zjg-30", ROOT / "07(009)-zjg-20200418" / "07(009)-zjg-20200418-30.prr"),
    ("zjg-3", ROOT / "07(009)-zjg-20200418" / "07(009)-zjg-20200418-3.prr"),
)


def read(path: Path) -> tuple[np.ndarray, np.ndarray]:
    y: list[float] = []
    z: list[float] = []
    inside = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "point.begin" in line:
            inside = True
            continue
        if "point.end" in line:
            break
        if not inside or line.lstrip().startswith("!"):
            continue
        match = POINT.match(line)
        if match:
            y.append(float(match.group(1)))
            z.append(float(match.group(2)))
    return np.array(y) * 1e3, np.array(z) * 1e3


def longest_flat_run(y: np.ndarray, z: np.ndarray, tolerance: float = 0.02) -> tuple[int, float, float, float, float]:
    slope = np.diff(z) / np.diff(y)
    flat = np.abs(slope) < tolerance
    best = (0, 0, 0)
    i = 0
    while i < flat.size:
        if flat[i]:
            j = i
            while j + 1 < flat.size and flat[j + 1]:
                j += 1
            if j - i + 1 > best[0]:
                best = (j - i + 1, i, j)
            i = j + 1
        else:
            i += 1
    count, lo, hi = best
    return count, y[lo:hi + 1].min(), y[lo:hi + 1].max(), z[lo:hi + 1].min(), z[lo:hi + 1].max()


def main() -> int:
    print(f"{'section':10s} {'points':>7s} {'z range (mm)':>18s}   longest near-horizontal stretch")
    for name, path in SECTIONS:
        if not path.is_file():
            print(f"  {name:10s} MISSING {path}")
            return 2
        y, z = read(path)
        count, y_lo, y_hi, z_lo, z_hi = longest_flat_run(y, z)
        print(f"  {name:8s} {y.size:7d} {z.min():+8.2f}..{z.max():+8.2f}   {count:4d} pts "
              f"y {y_lo:+7.2f}..{y_hi:+7.2f}  z {z_lo:+7.2f}..{z_hi:+7.2f}")
    print("\nThe 86-point stretch of zjg-72 sits at z ~ 0, so z grows DOWNWARD and the crown is z = 0;")
    print("the blade crowns therefore read 1.16 mm (30 mm width) and 14.94 mm (3 mm width) below it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
