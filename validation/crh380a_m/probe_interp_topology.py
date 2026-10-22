"""Check whether the frog running surface is lost by interpolating across a
topology change.

The vendor profile list mixes two naming families at nearly the same mileage:
regular running sections ``Profile_Mileage_R<station>.prr`` and special nose
sections ``Profile_Mileage_XG_*.prr`` / ``YG_*.prr``. Linear interpolation is
only meaningful inside one family; between a merged running section and a
point-rail-only section the interpolated upper envelope can sit below both
parents, which is exactly the 0.4-0.7 mm dip this project is chasing.

Usage:
    python -X utf8 probe_interp_topology.py
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

PROFILE_DIR = Path(r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database\wheel_rail_profiles")
RAIL_OFFSET = 0.753
BAND = (0.725, 0.800)


def envelope(name: str) -> tuple[np.ndarray, np.ndarray]:
    """Upper envelope (y, z_up) of one .prr file, metres, rail frame."""
    path = PROFILE_DIR / name
    text = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    points = []
    inside = False
    for line in text:
        token = line.strip()
        if token.startswith("point.begin"):
            inside = True
            continue
        if token.startswith("point.end"):
            inside = False
            continue
        if not inside:
            continue
        fields = token.split()
        if len(fields) < 2:
            continue
        try:
            points.append((float(fields[0]), float(fields[1])))
        except ValueError:
            continue
    raw = np.array(points, dtype=float)
    # z in the file grows downward from the crown: z_up = -z. y is measured from
    # the rail reference plane and is mapped to absolute lateral position by the
    # gauge offset the case uses.
    y = raw[:, 0] + RAIL_OFFSET
    z = -raw[:, 1]
    order = np.argsort(y, kind="stable")
    y, z = y[order], z[order]
    grid = np.arange(y[0], y[-1], 2.0e-5)
    merged = np.empty(grid.size, dtype=float)
    for index, value in enumerate(grid):
        left = np.searchsorted(y, value, side="right") - 1
        right = min(left + 1, y.size - 1)
        left = max(left, 0)
        if right == left:
            merged[index] = z[left]
        else:
            span = y[right] - y[left]
            weight = 0.0 if span <= 0 else (value - y[left]) / span
            merged[index] = z[left] + weight * (z[right] - z[left])
    return grid, merged


def band_surface(y: np.ndarray, z: np.ndarray) -> float:
    mask = (y >= BAND[0]) & (y <= BAND[1])
    return float(np.max(z[mask])) if mask.any() else float("nan")


def crown(y: np.ndarray, z: np.ndarray) -> tuple[float, float]:
    mask = (y >= BAND[0]) & (y <= BAND[1])
    if not mask.any():
        return float("nan"), float("nan")
    sub_y, sub_z = y[mask], z[mask]
    index = int(np.argmax(sub_z))
    return float(sub_y[index]), float(sub_z[index])


def interpolate(a: tuple[np.ndarray, np.ndarray], b: tuple[np.ndarray, np.ndarray],
                weight: float) -> tuple[np.ndarray, np.ndarray]:
    grid = np.arange(max(a[0][0], b[0][0]), min(a[0][-1], b[0][-1]), 2.0e-5)
    blended = ((1.0 - weight) * np.interp(grid, a[0], a[1])
               + weight * np.interp(grid, b[0], b[1]))
    return grid, blended


def main() -> int:
    pairs = [
        ("79.9206 R", "Profile_Mileage_R79.9206.prr", 79.9206,
         "79.9740 XG_GG", "Profile_Mileage_XG_GG.prr", 79.9740),
        ("79.9740 XG_GG", "Profile_Mileage_XG_GG.prr", 79.9740,
         "80.0044 R", "Profile_Mileage_R80.0044.prr", 80.0044),
        ("79.8672 R", "Profile_Mileage_R79.8672.prr", 79.8672,
         "79.9206 R", "Profile_Mileage_R79.9206.prr", 79.9206),
        ("79.4400 XG_FF", "Profile_Mileage_XG_FF.prr", 79.4400,
         "79.4934 R", "Profile_Mileage_R79.4934.prr", 79.4934),
    ]
    for label_a, file_a, s_a, label_b, file_b, s_b in pairs:
        env_a = envelope(file_a)
        env_b = envelope(file_b)
        ya, za = crown(*env_a)
        yb, zb = crown(*env_b)
        print(f"\n{label_a} -> {label_b}  (ds = {(s_b - s_a) * 1000:.1f} mm)")
        print(f"  crown A: y={ya * 1000:8.2f} mm  z={za * 1000:8.3f} mm")
        print(f"  crown B: y={yb * 1000:8.2f} mm  z={zb * 1000:8.3f} mm")
        for fraction in (0.25, 0.50, 0.75):
            grid, blended = interpolate(env_a, env_b, fraction)
            surface = band_surface(grid, blended)
            y_on = s_a + fraction * (s_b - s_a)
            print(f"  at s={y_on:.4f} ({fraction:.0%}): interpolated band surface "
                  f"{surface * 1000:8.3f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
