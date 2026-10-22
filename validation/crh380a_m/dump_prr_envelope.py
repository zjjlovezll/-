"""Upper envelope (minimum z, since z points down) of raw PRR contours.

Simpack stores a rail section as ONE closed contour with z measured downward
from the crown (z = 0 at the running surface, +29.9 at the foot).  The running
surface is therefore ``min z`` over the y bins.  Printing that envelope for the
frog sections settles whether the "1.7 mm dip" is in the source data or was
introduced by our own body segmentation.

Usage: python dump_prr_envelope.py <file.prr> [y_lo_mm y_hi_mm dy_mm]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database")


def parse(path: Path) -> np.ndarray:
    pts: list[tuple[float, float]] = []
    inside = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("point.begin"):
            inside = True
        elif s.startswith("point.end"):
            inside = False
        elif inside and s and not s.startswith("#"):
            f = s.split()
            if len(f) >= 2:
                try:
                    pts.append((float(f[0]) * 1e3, float(f[1]) * 1e3))
                except ValueError:
                    pass
    return np.asarray(pts, dtype=float)


def envelope(pts: np.ndarray, lo: float, hi: float, dy: float) -> tuple[np.ndarray, np.ndarray]:
    edges = np.arange(lo, hi + dy, dy)
    idx = np.clip(np.digitize(pts[:, 0], edges) - 1, 0, edges.size - 2)
    top = np.full(edges.size - 1, np.inf)
    np.minimum.at(top, idx, pts[:, 1])
    centers = 0.5 * (edges[:-1] + edges[1:])
    ok = np.isfinite(top)
    return centers[ok], top[ok]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    name = argv[1]
    lo = float(argv[2]) if len(argv) > 2 else -45.0
    hi = float(argv[3]) if len(argv) > 3 else 125.0
    dy = float(argv[4]) if len(argv) > 4 else 0.5
    path = next(iter(ROOT.rglob(name)), None)
    if path is None:
        raise SystemExit(f"not found: {name}")
    pts = parse(path)
    y, top = envelope(pts, lo, hi, dy)
    print(f"=== {name}  n={pts.size // 2}  dy={dy} mm   (z_up = -min_raw_z)")
    print(f"  {'y_mm':>8s} {'surface_mm':>11s}")
    for yi, zi in zip(y, top):
        print(f"  {yi:8.1f} {-zi:11.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
